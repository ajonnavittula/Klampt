#!/usr/bin/env python3
"""Convenience wrapper for managing the Klampt ROS2 Docker container.

This script mirrors the usability of Isaac Lab's ``docker/container.py``
utility.  It sets up X11 forwarding helpers (Xauthority, shared temp
folder), then delegates to ``docker compose`` to start, enter, or stop the
container described in ``docker-compose.yml``.

Typical usage (from the repository root)::

    ./docker/container.py start      # builds image, creates container
    ./docker/container.py enter      # open an interactive shell inside
    ./docker/container.py stop       # stop and remove the container

The script expects ``docker`` and ``xauth`` to be installed on the host.
You may also need to allow your local user access to the X server once per
session::

    xhost +SI:localuser:$(id -un)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
DEFAULT_TMP_DIR = Path(os.environ.get("KLAMPT_TMP_DIR", "/tmp/klampt-docker"))
DEFAULT_XAUTH = Path(os.environ.get("KLAMPT_XAUTH", DEFAULT_TMP_DIR / ".docker.xauth"))
DEFAULT_CONTAINER_NAME = os.environ.get("KLAMPT_CONTAINER_NAME", "klampt-ros2")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_tools() -> None:
    for tool in ("docker", "xauth"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"Required tool '{tool}' is not available on PATH.")


def _mutate_xauth_lines(raw: bytes) -> bytes:
    lines = []
    for line in raw.splitlines():
        if len(line) >= 4:
            line = b"ffff" + line[4:]
        lines.append(line)
    return b"\n".join(lines) + (b"\n" if lines else b"")


def _ensure_xauthority(tmp_dir: Path, xauth_path: Path, display: str | None) -> None:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    xauth_path.touch(mode=0o600, exist_ok=True)

    if not display:
        print("[WARN] DISPLAY is unset. GUI applications will not show from the container.")
        return

    result = subprocess.run(
        ["xauth", "nlist", display],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"[WARN] Failed to read Xauthority entries for display '{display}'.")
        return

    patched = _mutate_xauth_lines(result.stdout)
    subprocess.run(
        ["xauth", "-f", str(xauth_path), "nmerge", "-"],
        input=patched,
        check=False,
    )


def _compose_env(tmp_dir: Path, xauth_path: Path, container_name: str) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DISPLAY", env.get("DISPLAY", ""))
    env.setdefault("TERM", env.get("TERM", "xterm-256color"))
    env.setdefault("QT_X11_NO_MITSHM", "1")
    env["KLAMPT_TMP_DIR"] = str(tmp_dir)
    env["KLAMPT_XAUTH"] = str(xauth_path)
    env["KLAMPT_CONTAINER_NAME"] = container_name
    env.setdefault("XAUTHORITY", str(xauth_path))
    return env


def _compose_cmd(extra_args: Iterable[str]) -> List[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), *extra_args]


def _is_container_running(container_name: str) -> bool:
    result = subprocess.run(
        ["docker", "container", "inspect", "-f", "{{.State.Status}}", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "running"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> None:
    _ensure_tools()

    tmp_dir = Path(args.tmp_dir or DEFAULT_TMP_DIR)
    xauth_path = Path(args.xauth or DEFAULT_XAUTH)
    container_name = args.name or DEFAULT_CONTAINER_NAME

    _ensure_xauthority(tmp_dir, xauth_path, os.environ.get("DISPLAY"))

    env = _compose_env(tmp_dir, xauth_path, container_name)

    compose_args: List[str] = ["up", "--detach", "--remove-orphans"]
    if not args.no_build:
        compose_args.append("--build")
    if args.force_recreate:
        compose_args.append("--force-recreate")

    print(f"[INFO] Starting container '{container_name}' (docker compose {' '.join(compose_args)})")
    subprocess.run(_compose_cmd(compose_args), cwd=REPO_ROOT, env=env, check=True)
    print("[INFO] Container launch complete. Use './docker/container.py enter' to open a shell.")


def cmd_enter(args: argparse.Namespace) -> None:
    container_name = args.name or DEFAULT_CONTAINER_NAME
    if not _is_container_running(container_name):
        raise RuntimeError(f"Container '{container_name}' is not running. Start it first.")

    cmd = ["docker", "exec", "-it", container_name]
    if args.exec_cmd:
        cmd.extend(["bash", "-lc", args.exec_cmd])
    else:
        cmd.append("bash")
    subprocess.run(cmd, check=True)


def cmd_stop(args: argparse.Namespace) -> None:
    container_name = args.name or DEFAULT_CONTAINER_NAME
    env = _compose_env(Path(args.tmp_dir or DEFAULT_TMP_DIR), Path(args.xauth or DEFAULT_XAUTH), container_name)

    if not _is_container_running(container_name):
        print(f"[INFO] Container '{container_name}' is not running. Nothing to stop.")
    compose_args: List[str] = ["down"]
    if args.prune_volumes:
        compose_args.append("--volumes")
    if args.remove_images:
        compose_args.extend(["--rmi", "local"])

    subprocess.run(_compose_cmd(compose_args), cwd=REPO_ROOT, env=env, check=True)
    print(f"[INFO] Container '{container_name}' stopped.")


def cmd_status(args: argparse.Namespace) -> None:
    container_name = args.name or DEFAULT_CONTAINER_NAME
    running = _is_container_running(container_name)
    if running:
        print(f"Container '{container_name}' is running.")
    else:
        print(f"Container '{container_name}' is not running.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the Klampt ROS2 Docker container.")
    parser.add_argument(
        "command",
        choices=("start", "enter", "stop", "status"),
        help="Action to perform on the container.",
    )
    parser.add_argument("name", nargs="?", help="Override container name (defaults to klampt-ros2).")
    parser.add_argument(
        "--tmp-dir",
        dest="tmp_dir",
        help="Host directory to share with the container for temp files (default /tmp/klampt-docker).",
    )
    parser.add_argument(
        "--xauth",
        dest="xauth",
        help="Path to the generated Xauthority file (default <tmp-dir>/.docker.xauth).",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip rebuilding the image on start.",
    )
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Pass --force-recreate to docker compose up.",
    )
    parser.add_argument(
        "--prune-volumes",
        action="store_true",
        help="When stopping, also remove named/anonymous volumes.",
    )
    parser.add_argument(
        "--remove-images",
        action="store_true",
        help="When stopping, remove local images associated with the compose project.",
    )
    parser.add_argument(
        "--exec",
        dest="exec_cmd",
        help="Command to run via 'docker exec' for the enter action (default interactive bash).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    action = args.command

    if action == "start":
        cmd_start(args)
    elif action == "enter":
        cmd_enter(args)
    elif action == "stop":
        cmd_stop(args)
    elif action == "status":
        cmd_status(args)
    else:
        raise RuntimeError(f"Unhandled action '{action}'.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
