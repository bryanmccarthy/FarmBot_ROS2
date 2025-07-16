import os
from std_msgs.msg import String
from ament_index_python.packages import get_package_share_directory
from python_qt_binding import loadUi
from rqt_gui_py.plugin import Plugin
from PyQt5.QtWidgets import QWidget


class MovementPlugin(Plugin):
    def __init__(self, context):
        super(MovementPlugin, self).__init__(context)
        self.setObjectName('MovementPlugin')

        # Initialize ROS2 node
        self._node = context.node

        # Current position and increment
        self._cur_x = 0.0
        self._cur_y = 0.0
        self._cur_z = 0.0
        self._cur_increment = 10.0

        # Create QWidget
        self._widget = QWidget()

        # Get path to UI file
        ui_file = os.path.join(
            get_package_share_directory('farmbot_rqt_plugins'),
            'resource', 'movement.ui'
        )

        # Load UI file
        loadUi(ui_file, self._widget)

        # Create publisher for movement commands
        self._input_pub = self._node.create_publisher(
            String, 'input_topic', 10)

        # Create subscriber for position feedback
        self._uart_rx_sub = self._node.create_subscription(
            String, 'uart_receive', self._uart_feedback_callback, 10)

        # Connect UI signals
        self._connect_signals()

        # Add widget to the user interface
        context.add_widget(self._widget)

    def _connect_signals(self):
        '''
        Connect UI signals to their handlers
        '''
        # Connect directional buttons
        self._widget.button_up.clicked.connect(self._handle_up_clicked)
        self._widget.button_down.clicked.connect(self._handle_down_clicked)
        self._widget.button_left.clicked.connect(self._handle_left_clicked)
        self._widget.button_right.clicked.connect(self._handle_right_clicked)
        self._widget.button_home.clicked.connect(self._handle_home_clicked)

        # Connect increment radio buttons
        self._widget.radioButton_small.toggled.connect(
            self._handle_increment_changed)
        self._widget.radioButton_medium.toggled.connect(
            self._handle_increment_changed)
        self._widget.radioButton_large.toggled.connect(
            self._handle_increment_changed)

    def _handle_up_clicked(self):
        '''
        Handle Up button click - move in positive X direction
        '''
        self._send_command('w')

    def _handle_down_clicked(self):
        '''
        Handle Down button click - move in negative X direction
        '''
        self._send_command('s')

    def _handle_left_clicked(self):
        '''
        Handle Left button click - move in negative Y direction
        '''
        self._send_command('a')

    def _handle_right_clicked(self):
        '''
        Handle Right button click - move in positive Y direction
        '''
        self._send_command('d')

    def _handle_home_clicked(self):
        '''
        Handle Home button click - go to home position
        '''
        self._send_command('H_0')

    def _handle_increment_changed(self):
        '''
        Handle increment radio button change
        '''
        if self._widget.radioButton_small.isChecked():
            self._cur_increment = 10.0
            self._send_command('1')
        elif self._widget.radioButton_medium.isChecked():
            self._cur_increment = 100.0
            self._send_command('2')
        elif self._widget.radioButton_large.isChecked():
            self._cur_increment = 500.0
            self._send_command('3')

    def _send_command(self, cmd):
        '''
        Send a command to the farmbot controller
        '''
        msg = String()
        msg.data = cmd
        print(f"Sending: {msg.data}")  # TODO: remove
        self._input_pub.publish(msg)

    def _uart_feedback_callback(self, msg):
        '''
        Handle feedback from UART
        '''
        print(f"Received: {msg.data}")  # TODO: remove

        msg_split = msg.data.split(' ')
        report_code = msg_split[0]

        if report_code == 'R82':
            self._cur_x = float(msg_split[1][1:])
            self._cur_y = float(msg_split[2][1:])
            self._cur_z = float(msg_split[3][1:])

            # Update position display in UI
            self._widget.label_x_value.setText(f"{self._cur_x:.1f}")
            self._widget.label_y_value.setText(f"{self._cur_y:.1f}")
            self._widget.label_z_value.setText(f"{self._cur_z:.1f}")

    def shutdown_plugin(self):
        '''
        Clean up resources when plugin is shut down
        '''
        self._node.destroy_subscription(self._uart_rx_sub)
        self._node.destroy_publisher(self._input_pub)

    def save_settings(self, plugin_settings, instance_settings):
        '''
        Save settings when plugin is closed
        '''
        pass

    def restore_settings(self, plugin_settings, instance_settings):
        '''
        Restore settings when plugin is reopened
        '''
        pass
