# Docker Usage for Klampt with ROS2

## Building the Docker Image

The Dockerfile.ros2 now builds Klampt and installs the Python bindings during the image build process.

```bash
# Build the image (this will compile Klampt with ROS2 support)
docker compose build klampt-ros2
```

## Running the Container

```bash
# Start an interactive bash session
docker compose run --rm klampt-ros2 bash

# Once inside the container, test the installation
python3 -c "import klampt; print('Klampt version:', klampt.__version__)"
```

## What Gets Built

During the Docker build:
1. **Dependencies**: KrisLibrary and ODE are built and installed system-wide
2. **ROS2 Integration**: All ROS2 packages for Humble are installed
3. **Klampt C++ Library**: Built with ROS2 support at `/opt/Klampt/build`
4. **Python Bindings**: Installed to Python site-packages with proper ROS2 linking

## Development Workflow

The container mounts your workspace at `/workspace` for development. If you make changes to the Klampt source code:

### Option 1: Rebuild the Container Image
```bash
docker compose build klampt-ros2
```

### Option 2: Rebuild Inside the Container (faster for testing)
```bash
# Inside the container
cd /workspace
mkdir -p build && cd build
cmake .. -DKLAMPT_ROS_VERSION=ROS2
make -j$(nproc)
make python
```

## Environment Variables

The following are automatically set:
- `AMENT_PREFIX_PATH=/opt/ros/humble`
- `LD_LIBRARY_PATH=/usr/local/lib:/opt/ros/humble/lib`
- `PYTHON3=/usr/bin/python3`

ROS2 environment is sourced automatically via the entrypoint script.

## Verifying ROS2 Integration

```bash
# Check that ROS2 symbols are properly linked
python3 -c "import klampt; print('ROS2 support built-in')"

# Or check the shared library directly
ldd /usr/local/lib/python3.10/dist-packages/klampt/_robotsim.*.so | grep rclcpp
```
