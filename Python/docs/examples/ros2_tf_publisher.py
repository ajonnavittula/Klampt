#!/usr/bin/env python3
"""Minimal ROS 2 TF tree publisher for a Klamp't robot model.

Example usage:

    source /opt/ros/humble/setup.bash
    export PYTHONPATH=/workspace/.pyuser/lib/python3.10/site-packages:$PYTHONPATH
    python Python/docs/examples/ros2_tf_publisher.py \
        --world /path/to/my_robot.world --robot-index 0 \
        --frame-prefix klampt --reference-frame world

The script loads the specified Klamp't world / robot file, optionally applies
the provided joint configuration, and continuously publishes the link frames
on /tf so that standard ROS 2 TF tools can visualize / introspect the tree.
"""

import argparse
import os
from typing import List, Optional, Sequence, Tuple

import rclpy
from geometry_msgs.msg import TransformStamped
from klampt import WorldModel
from klampt.math import so3
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


def _child_frame_name(base: str, prefix: str) -> str:
    """Apply an optional TF prefix while keeping frame IDs tidy."""
    if not prefix:
        return base
    prefix = prefix.rstrip('/')
    return f"{prefix}/{base}"


class KlamptTfPublisher(Node):
    """ROS 2 node that publishes the TF tree for a Klamp't robot."""

    def __init__(
        self,
        world_path: str,
        robot_index: int,
        frame_prefix: str,
        reference_frame: str,
        publish_rate: float,
        configuration: Optional[Sequence[float]],
    ) -> None:
        super().__init__('klampt_tf_publisher')
        if publish_rate <= 0.0:
            raise ValueError('Publish rate must be positive')
        self._world = WorldModel()
        if not os.path.exists(world_path):
            raise FileNotFoundError(world_path)
        if not self._world.readFile(world_path):
            raise RuntimeError(f'Unable to load Klamp\'t world from {world_path}')
        if robot_index < 0 or robot_index >= self._world.numRobots():
            raise IndexError(
                f'Robot index {robot_index} out of range (found {self._world.numRobots()} robots)'
            )
        self._robot = self._world.robot(robot_index)

        robot_config = self._robot.getConfig()
        if configuration is not None:
            if len(configuration) != len(robot_config):
                raise ValueError(
                    f'Configuration length {len(configuration)} does not match robot DOF {len(robot_config)}'
                )
            self._robot.setConfig(list(configuration))

        self._reference_frame = reference_frame
        self._frame_prefix = frame_prefix
        self._child_frames: List[str] = []
        self._parent_frames: List[str] = []
        self._precompute_frames()

        self._tf_broadcaster = TransformBroadcaster(self)
        self._timer = self.create_timer(1.0 / publish_rate, self._publish_tf)
        self.get_logger().info(
            f'Publishing TF tree for robot "{self._robot.getName()}" at {publish_rate:.2f} Hz'
        )

    def _precompute_frames(self) -> None:
        """Cache frame names for each link for efficiency."""
        self._child_frames.clear()
        self._parent_frames.clear()
        for link_index in range(self._robot.numLinks()):
            link = self._robot.link(link_index)
            base_name = link.getName() or f'link_{link_index}'
            child_frame = _child_frame_name(base_name, self._frame_prefix)
            parent_index = link.getParent()
            if parent_index < 0:
                parent_frame = self._reference_frame
            else:
                parent_name = self._robot.link(parent_index).getName() or f'link_{parent_index}'
                parent_frame = _child_frame_name(parent_name, self._frame_prefix)
            self._child_frames.append(child_frame)
            self._parent_frames.append(parent_frame)

    def _publish_tf(self) -> None:
        """Publish the transform tree for every link in the robot."""
        stamp = self.get_clock().now().to_msg()
        transforms: List[TransformStamped] = []
        for link_index in range(self._robot.numLinks()):
            link = self._robot.link(link_index)
            rotation, translation = link.getTransform()
            quat = so3.quaternion(rotation)
            tf_msg = TransformStamped()
            tf_msg.header.stamp = stamp
            tf_msg.header.frame_id = self._parent_frames[link_index]
            tf_msg.child_frame_id = self._child_frames[link_index]
            tf_msg.transform.translation.x = translation[0]
            tf_msg.transform.translation.y = translation[1]
            tf_msg.transform.translation.z = translation[2]
            tf_msg.transform.rotation.x = quat[0]
            tf_msg.transform.rotation.y = quat[1]
            tf_msg.transform.rotation.z = quat[2]
            tf_msg.transform.rotation.w = quat[3]
            transforms.append(tf_msg)
        if transforms:
            self._tf_broadcaster.sendTransform(transforms)


def _parse_arguments() -> Tuple[argparse.Namespace, List[str]]:
    parser = argparse.ArgumentParser(description='Publish a TF tree for a Klamp\'t robot model.')
    parser.add_argument(
        '--world',
        required=True,
        help='Path to the Klamp\'t world/robot file (.rob, .xml, or compatible).',
    )
    parser.add_argument(
        '--robot-index',
        type=int,
        default=0,
        help='Which robot from the world file to broadcast (default: 0).',
    )
    parser.add_argument(
        '--frame-prefix',
        type=str,
        default='',
        help='Optional TF prefix applied to every robot link frame.',
    )
    parser.add_argument(
        '--reference-frame',
        type=str,
        default='world',
        help='Frame ID used as the parent of the root link (default: world).',
    )
    parser.add_argument(
        '--rate',
        type=float,
        default=10.0,
        help='Publish frequency in Hz (default: 10).',
    )
    parser.add_argument(
        '--config',
        type=float,
        nargs='*',
        help='Optional joint configuration (space separated list of floats).',
    )
    return parser.parse_known_args()


def main() -> None:
    args, ros_args = _parse_arguments()
    rclpy.init(args=ros_args)
    node = KlamptTfPublisher(
        world_path=args.world,
        robot_index=args.robot_index,
        frame_prefix=args.frame_prefix,
        reference_frame=args.reference_frame,
        publish_rate=args.rate,
        configuration=args.config,
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
