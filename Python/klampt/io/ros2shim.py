"""Lightweight shim that emulates the parts of rospy used by Klamp't, backed by
ROS 2's rclpy API."""

import threading

try:
    import rclpy
    from builtin_interfaces.msg import Duration as BuiltinDuration
    from builtin_interfaces.msg import Time as BuiltinTime
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.parameter import Parameter
    from rclpy.qos import QoSProfile
    from rclpy.time import Time as RclTime
    from rclpy.duration import Duration as RclDuration
except ImportError as ex:  # pragma: no cover - handled by caller
    raise

_node = None
_node_lock = threading.Lock()
_executor = None
_executor_thread = None
_PARAM_UNSET = object()


def _start_executor():
    global _executor_thread
    if _executor_thread is None:
        _executor_thread = threading.Thread(target=_executor.spin, daemon=True)
        _executor_thread.start()


def init_node(name):
    """Initializes (or returns) the shared ROS 2 node."""
    global _node, _executor
    with _node_lock:
        if _node is not None:
            return _node
        if not rclpy.is_initialized():
            rclpy.init(args=None)
        _node = rclpy.create_node(name)
        _executor = SingleThreadedExecutor()
        _executor.add_node(_node)
        _start_executor()
        return _node


def get_node():
    """Returns the shared node, creating it if needed."""
    if _node is None:
        init_node('klampt')
    return _node


def shutdown():
    """Stops the executor and shuts down rclpy."""
    global _node, _executor, _executor_thread
    with _node_lock:
        if _executor:
            _executor.shutdown()
            _executor = None
        _executor_thread = None
        if _node is not None:
            _node.destroy_node()
            _node = None
        if rclpy.is_initialized():
            rclpy.shutdown()


class Time(BuiltinTime):
    """ROS 1 style rospy.Time implemented on top of builtin_interfaces/Time."""

    def __init__(self, value=None, nsecs=None):
        super().__init__()
        if value is None:
            self.sec = 0
            self.nanosec = 0
        elif nsecs is not None:
            self.sec = int(value)
            self.nanosec = int(nsecs)
        else:
            self._assign(value)

    def _assign(self, value):
        if isinstance(value, Time):
            self.sec = value.sec
            self.nanosec = value.nanosec
        elif isinstance(value, BuiltinTime):
            self.sec = value.sec
            self.nanosec = value.nanosec
        elif isinstance(value, RclTime):
            msg = value.to_msg()
            self.sec = msg.sec
            self.nanosec = msg.nanosec
        elif hasattr(value, 'sec') and hasattr(value, 'nanosec'):
            self.sec = int(value.sec)
            self.nanosec = int(value.nanosec)
        elif isinstance(value, (int, float)):
            self.sec = int(value)
            self.nanosec = int((value - int(value)) * 1e9)
        else:
            raise TypeError("Unsupported value for Time: {}".format(type(value)))

    @staticmethod
    def now():
        """Returns the current ROS time."""
        now = get_node().get_clock().now()
        return Time(now)

    @staticmethod
    def from_sec(value):
        """Builds a Time from seconds."""
        return Time(value)

    def to_sec(self):
        return float(self.sec) + float(self.nanosec) * 1e-9

    def to_msg(self):
        return BuiltinTime(sec=self.sec, nanosec=self.nanosec)

    def __float__(self):
        return self.to_sec()


class Duration(BuiltinDuration):
    """ROS 1 style rospy.Duration."""

    def __init__(self, value=None, nsecs=None):
        super().__init__()
        if value is None:
            self.sec = 0
            self.nanosec = 0
        elif nsecs is not None:
            self.sec = int(value)
            self.nanosec = int(nsecs)
        else:
            self._assign(value)

    def _assign(self, value):
        if isinstance(value, Duration):
            self.sec = value.sec
            self.nanosec = value.nanosec
        elif isinstance(value, BuiltinDuration):
            self.sec = value.sec
            self.nanosec = value.nanosec
        elif isinstance(value, RclDuration):
            msg = value.to_msg()
            self.sec = msg.sec
            self.nanosec = msg.nanosec
        elif hasattr(value, 'sec') and hasattr(value, 'nanosec'):
            self.sec = int(value.sec)
            self.nanosec = int(value.nanosec)
        elif isinstance(value, (int, float)):
            self.sec = int(value)
            self.nanosec = int((value - int(value)) * 1e9)
        else:
            raise TypeError("Unsupported value for Duration: {}".format(type(value)))

    @staticmethod
    def from_sec(value):
        return Duration(value)

    def to_sec(self):
        return float(self.sec) + float(self.nanosec) * 1e-9

    def to_msg(self):
        return BuiltinDuration(sec=self.sec, nanosec=self.nanosec)


class Publisher:
    """Minimal stand-in for rospy.Publisher."""

    def __init__(self, topic, msg_type, queue_size=10, **kwargs):
        qos = QoSProfile(depth=queue_size)
        self._node = get_node()
        self._publisher = self._node.create_publisher(msg_type, topic, qos_profile=qos)
        self.name = topic

    def publish(self, msg):
        self._publisher.publish(msg)

    def unregister(self):
        if self._publisher is not None:
            self._node.destroy_publisher(self._publisher)
            self._publisher = None


class Subscriber:
    """Minimal stand-in for rospy.Subscriber."""

    def __init__(self, topic, msg_type, callback, queue_size=10, **kwargs):
        qos = QoSProfile(depth=queue_size)
        self._node = get_node()
        self._subscription = self._node.create_subscription(msg_type, topic, callback, qos)
        self.name = topic

    def unregister(self):
        if self._subscription is not None:
            self._node.destroy_subscription(self._subscription)
            self._subscription = None


def get_rostime():
    """Returns the current time (rospy.get_rostime equivalent)."""
    return Time.now()


def _normalize_param_name(name):
    """Converts ROS 1 style names (/foo/bar) to ROS 2 friendly ones (foo.bar)."""
    return name.lstrip('/').replace('/', '.')


def get_param(name, default=_PARAM_UNSET):
    """Fetches a parameter, declaring it if necessary."""
    node = get_node()
    norm = _normalize_param_name(name)
    if not node.has_parameter(norm):
        if default is _PARAM_UNSET:
            raise KeyError("Parameter {} not set".format(name))
        node.declare_parameter(norm, default)
    return node.get_parameter(norm).value


def set_param(name, value):
    """Sets (or declares) a node parameter."""
    node = get_node()
    norm = _normalize_param_name(name)
    if not node.has_parameter(norm):
        node.declare_parameter(norm, value)
    else:
        param = Parameter(name=norm, value=value)
        node.set_parameters([param])
