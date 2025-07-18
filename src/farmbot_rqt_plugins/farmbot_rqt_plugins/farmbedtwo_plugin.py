import os
import yaml
from ament_index_python.packages import get_package_share_directory

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainter, QFont, QPolygonF, QPixmap
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsTextItem,
    QGraphicsRectItem,
    QScrollBar,
    QSplitter,
    QLabel,
    QPushButton,
    QFrame,
    QCheckBox,
)

from rqt_gui_py.plugin import Plugin
from std_msgs.msg import String

# Temp Constants TODO: remove
WIDTH = 6000
HEIGHT = 3000


class FarmbedTwoPlugin(Plugin):
    def __init__(self, context):
        super(FarmbedTwoPlugin, self).__init__(context)
        self.setObjectName("FarmbedTwoPlugin")

        # Initialize ROS2 node
        self._node = context.node

        # Initialize gantry position TODO: fix
        self.gantry_x = 300.0
        self.gantry_y = 300.0
        self.gantry_z = 0.0

        # Create subscriber for gantry position feedback
        self._uart_rx_sub = self._node.create_subscription(
            String, 'uart_receive', self._uart_feedback_callback, 10)

        # Initialize map data
        self.active_map = None
        self.map_x = 0
        self.map_y = 0
        self.plant_positions = []
        self.plant_data = []

        # Load all plant icons once during initialization
        self.plant_icons = self._load_all_plant_icons()
        self.plant_icon_size = 32  # Base icon size

        # Selected plant tracking
        self.selected_plant = None

        # Initialize zoom state
        self.zoom_factor = 1.0
        self.zoom_min = 0.1
        self.zoom_max = 4.0
        self.zoom_step = 0.1

        # Toggle states
        self.show_canopy_radius = True
        self.show_plant_indices = False
        self.show_plant_names = False

        # Gantry graphics items
        self.gantry_bar = None
        self.gantry_position = None

        # Mouse panning state
        self.is_panning = False
        self.last_pan_point = None
        self.click_start_pos = None
        self.drag_threshold = 5

        # Load active map
        self._load_active_map()

        # Create main widget
        self._widget = QWidget()
        self._widget.keyPressEvent = self.keyPressEvent

        # Create main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create horizontal splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Create left side panel
        self._left_panel = self._create_left_panel()
        splitter.addWidget(self._left_panel)

        # Create right side widget for the grid
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Create grid layout with labels
        grid_layout = self._create_grid_with_labels()
        right_layout.addLayout(grid_layout)

        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([150, 800])

        main_layout.addWidget(splitter)
        self._widget.setLayout(main_layout)
        context.add_widget(self._widget)

        # Enable focus to receive key events
        self._widget.setFocusPolicy(Qt.StrongFocus)

    def _uart_feedback_callback(self, msg):
        """Handle feedback from UART to update gantry position"""
        try:
            msg_split = msg.data.split(' ')
            report_code = msg_split[0]

            if report_code == 'R82' and len(msg_split) >= 4:
                self.gantry_x = float(msg_split[1][1:])  # Remove 'X' prefix
                self.gantry_y = float(msg_split[2][1:])  # Remove 'Y' prefix
                self.gantry_z = float(msg_split[3][1:])  # Remove 'Z' prefix

                # Redraw gantry position
                self._redraw_gantry()
        except (ValueError, IndexError) as e:
            self._node.get_logger().warning(
                f'Error parsing UART feedback: {e}')

    def _create_left_panel(self):
        """Create the left side panel split into toggles and plant details"""
        panel = QWidget()
        # Set minimum width to prevent it from getting too small
        panel.setMinimumWidth(150)
        # Same brown as axis labels
        panel.setStyleSheet("background-color: #C3A582;")

        # Create vertical layout for panel content
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Create toggles section (top half)
        toggles_widget = self._create_toggles_section()
        layout.addWidget(toggles_widget)

        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #2b2b2b;")
        layout.addWidget(separator)

        # Create plant details section (bottom half)
        self.plant_details_widget = QWidget()
        self.plant_details_layout = QVBoxLayout()
        self.plant_details_layout.setContentsMargins(0, 0, 0, 0)

        self.no_selection_label = QLabel("No plant selected")
        self.no_selection_label.setStyleSheet(
            "color: #2b2b2b; font-size: 11px; font-style: italic;")
        self.plant_details_layout.addWidget(self.no_selection_label)

        self.plant_details_widget.setLayout(self.plant_details_layout)
        layout.addWidget(self.plant_details_widget)

        # Add stretch to push content to top
        layout.addStretch()

        panel.setLayout(layout)
        return panel

    def _create_toggles_section(self):
        """Create the toggles section for the top half of left panel"""
        toggles_widget = QWidget()
        toggles_layout = QVBoxLayout()
        toggles_layout.setContentsMargins(0, 0, 0, 0)
        toggles_layout.setSpacing(10)

        # Section title
        toggles_title = QLabel("Display Options")
        toggles_title.setFont(QFont("Arial", 10, QFont.Bold))
        toggles_title.setStyleSheet("color: #2b2b2b;")
        toggles_layout.addWidget(toggles_title)

        # Zoom control buttons
        zoom_layout = QHBoxLayout()
        zoom_layout.setContentsMargins(0, 5, 0, 0)
        zoom_layout.setSpacing(5)

        # Zoom in button
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setFixedSize(25, 25)
        self.zoom_in_button.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """)
        self.zoom_in_button.clicked.connect(self._zoom_in)
        zoom_layout.addWidget(self.zoom_in_button)

        # Zoom out button
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setFixedSize(25, 25)
        self.zoom_out_button.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """)
        self.zoom_out_button.clicked.connect(self._zoom_out)
        zoom_layout.addWidget(self.zoom_out_button)

        # Add stretch to push buttons to left
        zoom_layout.addStretch()

        toggles_layout.addLayout(zoom_layout)

        # Canopy radius toggle
        self.canopy_checkbox = QCheckBox("Show Canopy Radius")
        self.canopy_checkbox.setChecked(self.show_canopy_radius)
        self.canopy_checkbox.setStyleSheet("""
            QCheckBox {
                color: #2b2b2b;
                font-size: 9px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #2b2b2b;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #2b2b2b;
                background-color: #2b2b2b;
            }
        """)
        self.canopy_checkbox.stateChanged.connect(self._toggle_canopy_radius)
        toggles_layout.addWidget(self.canopy_checkbox)

        # Plant indices toggle
        self.indices_checkbox = QCheckBox("Show Plant Indices")
        self.indices_checkbox.setChecked(self.show_plant_indices)
        self.indices_checkbox.setStyleSheet("""
            QCheckBox {
                color: #2b2b2b;
                font-size: 9px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #2b2b2b;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #2b2b2b;
                background-color: #2b2b2b;
            }
        """)
        self.indices_checkbox.stateChanged.connect(self._toggle_plant_indices)
        toggles_layout.addWidget(self.indices_checkbox)

        # Plant names toggle
        self.names_checkbox = QCheckBox("Show Plant Names")
        self.names_checkbox.setChecked(self.show_plant_names)
        self.names_checkbox.setStyleSheet("""
            QCheckBox {
                color: #2b2b2b;
                font-size: 9px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #2b2b2b;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #2b2b2b;
                background-color: #2b2b2b;
            }
        """)
        self.names_checkbox.stateChanged.connect(self._toggle_plant_names)
        toggles_layout.addWidget(self.names_checkbox)

        toggles_widget.setLayout(toggles_layout)
        return toggles_widget

    def _toggle_canopy_radius(self, state):
        """Toggle canopy radius visibility"""
        self.show_canopy_radius = state == Qt.Checked
        self._redraw_plants()

    def _toggle_plant_indices(self, state):
        """Toggle plant indices visibility"""
        self.show_plant_indices = state == Qt.Checked
        self._redraw_plants()

    def _toggle_plant_names(self, state):
        """Toggle plant names visibility"""
        self.show_plant_names = state == Qt.Checked
        self._redraw_plants()

    def _update_plant_details(self, plant_data):
        """Update the left panel with selected plant details"""
        # Clear existing content
        for i in reversed(range(self.plant_details_layout.count())):
            self.plant_details_layout.itemAt(i).widget().setParent(None)

        if plant_data:
            self.selected_plant = plant_data

            # Find plant index
            plant_index = None
            for idx, plant in enumerate(self.plant_data):
                if plant["x"] == plant_data["x"] and plant["y"] == plant_data["y"]:
                    plant_index = idx
                    break

            # Plant Index (prominent display)
            if plant_index is not None:
                index_label = QLabel(f"Plant {plant_index}")
                index_label.setFont(QFont("Arial", 14, QFont.Bold))
                index_label.setStyleSheet(
                    "color: #2b2b2b; background-color: rgba(255,255,255,0.3); padding: 5px; border-radius: 3px; margin-bottom: 5px;")
                self.plant_details_layout.addWidget(index_label)

            # Create info labels with values (no header)
            label_style = "color: #2b2b2b; font-size: 10px; padding: 1px; margin: 1px;"
            field_style = "color: #2b2b2b; font-size: 9px; font-weight: bold; margin: 1px;"

            name_field = QLabel("Name:")
            name_field.setStyleSheet(field_style)
            name_value = QLabel(plant_data["name"])
            name_value.setStyleSheet(label_style + "font-weight: bold;")
            self.plant_details_layout.addWidget(name_field)
            self.plant_details_layout.addWidget(name_value)

            pos_field = QLabel("Position:")
            pos_field.setStyleSheet(field_style)
            pos_value = QLabel(
                f"({plant_data['x']:.1f}, {plant_data['y']:.1f}, {plant_data.get('z', 0):.1f})")
            pos_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(pos_field)
            self.plant_details_layout.addWidget(pos_value)

            stage_field = QLabel("Growth Stage:")
            stage_field.setStyleSheet(field_style)
            stage_value = QLabel(plant_data.get("growth_stage", "Unknown"))
            stage_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(stage_field)
            self.plant_details_layout.addWidget(stage_value)

            date_field = QLabel("Plant Date:")
            date_field.setStyleSheet(field_style)
            date_value = QLabel(plant_data.get("plant_date", "Unknown"))
            date_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(date_field)
            self.plant_details_layout.addWidget(date_value)

            canopy_field = QLabel("Canopy Radius:")
            canopy_field.setStyleSheet(field_style)
            canopy_value = QLabel(f"{plant_data['canopy_radius']:.1f}mm")
            canopy_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(canopy_field)
            self.plant_details_layout.addWidget(canopy_value)

            max_height_field = QLabel("Max Height:")
            max_height_field.setStyleSheet(field_style)
            max_height_value = QLabel(
                f"{plant_data.get('max_height', 0):.1f}mm")
            max_height_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(max_height_field)
            self.plant_details_layout.addWidget(max_height_value)

            plant_radius_field = QLabel("Plant Radius:")
            plant_radius_field.setStyleSheet(field_style)
            plant_radius_value = QLabel(
                f"{plant_data.get('plant_radius', 0):.1f}mm")
            plant_radius_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(plant_radius_field)
            self.plant_details_layout.addWidget(plant_radius_value)

            water_field = QLabel("Water Quantity:")
            water_field.setStyleSheet(field_style)
            water_value = QLabel(f"{plant_data.get('water_quantity', 0):.1f}")
            water_value.setStyleSheet(label_style)
            self.plant_details_layout.addWidget(water_field)
            self.plant_details_layout.addWidget(water_value)
        else:
            self.selected_plant = None
            self.no_selection_label = QLabel("No plant selected")
            self.no_selection_label.setStyleSheet(
                "color: #2b2b2b; font-size: 11px; font-style: italic;")
            self.plant_details_layout.addWidget(self.no_selection_label)

    def _on_graphics_view_mouse_press(self, event):
        """Handle mouse press events on the graphics view"""
        if event.button() == Qt.LeftButton:
            # Store the click start position for drag
            self.click_start_pos = event.pos()
        elif event.button() == Qt.MiddleButton:
            # Start panning with middle mouse button
            self.is_panning = True
            self.last_pan_point = event.pos()
            self._graphics_view.setCursor(Qt.ClosedHandCursor)

    def _on_graphics_view_mouse_move(self, event):
        """Handle mouse move events on the graphics view"""
        # Check if we should start left-click drag panning
        if (self.click_start_pos is not None and
            not self.is_panning and
                (event.buttons() & Qt.LeftButton)):

            # Calculate distance from click start
            drag_distance = (
                event.pos() - self.click_start_pos).manhattanLength()

            if drag_distance > self.drag_threshold:
                # Start panning
                self.is_panning = True
                self.last_pan_point = event.pos()
                self._graphics_view.setCursor(Qt.ClosedHandCursor)

        # Handle panning (both middle-click and left-click drag)
        if self.is_panning and self.last_pan_point is not None:
            delta = event.pos() - self.last_pan_point

            # Get current scrollbar values
            h_bar = self._graphics_view.horizontalScrollBar()
            v_bar = self._graphics_view.verticalScrollBar()

            # Update scrollbar positions
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

            # Update last pan point
            self.last_pan_point = event.pos()

    def _on_graphics_view_mouse_release(self, event):
        """Handle mouse release events on the graphics view"""
        if event.button() == Qt.LeftButton:
            if self.is_panning:
                # End left-click drag panning
                self.is_panning = False
                self.last_pan_point = None
                self._graphics_view.setCursor(Qt.ArrowCursor)
            elif self.click_start_pos is not None:
                # Handle plant selection click
                drag_distance = (
                    event.pos() - self.click_start_pos).manhattanLength()
                if drag_distance <= self.drag_threshold:
                    # Convert click position to scene coordinates
                    scene_pos = self._graphics_view.mapToScene(event.pos())
                    click_x = scene_pos.x()
                    click_y = scene_pos.y()

                    # Check if click is near any plant
                    clicked_plant = self._get_plant_at_position(
                        click_x, click_y)
                    if clicked_plant:
                        self._update_plant_details(clicked_plant)
                    else:
                        # Clear selection if clicking empty space
                        self._update_plant_details(None)

            # Reset click start position
            self.click_start_pos = None

        elif event.button() == Qt.MiddleButton and self.is_panning:
            # End middle-click panning
            self.is_panning = False
            self.last_pan_point = None
            self._graphics_view.setCursor(Qt.ArrowCursor)

    def _get_plant_at_position(self, x, y):
        """Check if the click position is within any plant's icon/circle"""
        click_radius = 40

        for plant in self.plant_data:
            plant_x = plant["x"]
            plant_y = plant["y"]

            # Calculate distance from click to plant center
            distance = ((x - plant_x) ** 2 + (y - plant_y) ** 2) ** 0.5

            if distance <= click_radius:
                return plant

        return None

    def _create_grid_with_labels(self):
        """Create the grid view with axis labels"""
        # Create vertical layout for the entire grid area
        grid_layout = QVBoxLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Create horizontal layout for top labels + corner space
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Add corner space (for Y-axis label area)
        corner_widget = QWidget()
        corner_widget.setFixedSize(30, 30)
        corner_widget.setStyleSheet("background-color: #C3A582;")
        top_layout.addWidget(corner_widget)

        # Create top label widget for X-axis
        self._top_labels = AxisLabelWidget(
            WIDTH, True, padding_right=50
        )  # Add right padding
        self._top_labels.setFixedHeight(30)
        top_layout.addWidget(self._top_labels)

        grid_layout.addLayout(top_layout)

        # Create horizontal layout for left labels + graphics view
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Create left label widget for Y-axis
        self._left_labels = AxisLabelWidget(
            HEIGHT, False, padding_bottom=50
        )  # Add bottom padding
        self._left_labels.setFixedWidth(30)
        content_layout.addWidget(self._left_labels)

        # Create graphics view with scene
        self._graphics_view = QGraphicsView()
        self._scene = QGraphicsScene()
        self._scene.setSceneRect(0, 0, WIDTH, HEIGHT)
        self._graphics_view.setScene(self._scene)

        # Enable mouse tracking for plant selection and panning
        self._graphics_view.mousePressEvent = self._on_graphics_view_mouse_press
        self._graphics_view.mouseMoveEvent = self._on_graphics_view_mouse_move
        self._graphics_view.mouseReleaseEvent = self._on_graphics_view_mouse_release
        self._graphics_view.setMouseTracking(True)

        # Disable built-in scrollbars
        self._graphics_view.setFrameStyle(0)
        self._graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._graphics_view.setStyleSheet(
            "background-color: #D2B48C;"
        )  # Light brown bg

        # Create external scrollbars
        self._h_scrollbar = QScrollBar(Qt.Horizontal)
        self._v_scrollbar = QScrollBar(Qt.Vertical)

        # Style scrollbars
        scrollbar_style = """
            QScrollBar {
                background-color: #C3A582;
            }
            QScrollBar:horizontal {
                height: 30px;
            }
            QScrollBar:vertical {
                width: 30px;
            }
            QScrollBar::handle {
                background-color: #2b2b2b;
                border-radius: 6px;
                min-height: 20px;
                min-width: 20px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0px;
                height: 0px;
                border: none;
                background: none;
            }
        """
        self._h_scrollbar.setStyleSheet(scrollbar_style)
        self._v_scrollbar.setStyleSheet(scrollbar_style)

        # Connect external scrollbars to graphics view
        self._h_scrollbar.valueChanged.connect(
            self._graphics_view.horizontalScrollBar().setValue
        )
        self._v_scrollbar.valueChanged.connect(
            self._graphics_view.verticalScrollBar().setValue
        )
        self._graphics_view.horizontalScrollBar().valueChanged.connect(
            self._h_scrollbar.setValue
        )
        self._graphics_view.verticalScrollBar().valueChanged.connect(
            self._v_scrollbar.setValue
        )

        # Sync scrollbar ranges
        self._graphics_view.horizontalScrollBar().rangeChanged.connect(
            self._h_scrollbar.setRange
        )
        self._graphics_view.verticalScrollBar().rangeChanged.connect(
            self._v_scrollbar.setRange
        )

        # Connect scroll events to update labels
        self._h_scrollbar.valueChanged.connect(self._update_label_positions)
        self._v_scrollbar.valueChanged.connect(self._update_label_positions)

        # Create grid
        self._create_grid()

        # Draw plants
        self._draw_plant_icons()

        content_layout.addWidget(self._graphics_view)
        content_layout.addWidget(self._v_scrollbar)
        grid_layout.addLayout(content_layout)

        # Add horizontal scrollbar at the bottom
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)
        # Left spacer to match Y-axis label width
        left_spacer = QWidget()
        left_spacer.setFixedWidth(30)
        left_spacer.setStyleSheet("background-color: #C3A582;")  # Darker brown
        bottom_layout.addWidget(left_spacer)
        bottom_layout.addWidget(self._h_scrollbar)
        # Right spacer to match vertical scrollbar width
        right_spacer = QWidget()
        right_spacer.setFixedWidth(self._v_scrollbar.sizeHint().width())
        right_spacer.setStyleSheet(
            "background-color: #C3A582;")  # Darker brown
        bottom_layout.addWidget(right_spacer)
        grid_layout.addLayout(bottom_layout)

        return grid_layout

    def _update_label_positions(self):
        """Update label positions when scrolling"""
        # Get current scroll positions
        h_value = self._graphics_view.horizontalScrollBar().value()
        v_value = self._graphics_view.verticalScrollBar().value()

        # Update label offsets
        self._top_labels.set_offset(-h_value)
        self._left_labels.set_offset(-v_value)

    def _create_grid(self):
        """Create grid lines every 10mm"""
        thin_pen = QPen(QColor(139, 119, 93), 0.3)  # Thin lines for 10mm
        thick_pen = QPen(QColor(139, 119, 93), 1.0)  # Thick lines for 100mm

        # Vertical lines every 10mm
        for x in range(0, WIDTH + 1, 10):
            pen = thick_pen if x % 100 == 0 else thin_pen
            line = QGraphicsLineItem(x, 0, x, HEIGHT)
            line.setPen(pen)
            self._scene.addItem(line)

        # Horizontal lines every 10mm
        for y in range(0, HEIGHT + 1, 10):
            pen = thick_pen if y % 100 == 0 else thin_pen
            line = QGraphicsLineItem(0, y, WIDTH, y)
            line.setPen(pen)
            self._scene.addItem(line)

        # Draw initial gantry position
        self._draw_gantry()

    def _draw_gantry(self):
        """Draw gantry bar and position indicator"""
        # Remove existing gantry items
        if self.gantry_bar:
            self._scene.removeItem(self.gantry_bar)
        if self.gantry_position:
            self._scene.removeItem(self.gantry_position)

        transparent_gray = QColor(128, 128, 128, 128)  # 50% transparent gray

        # Draw gantry bar
        gantry_pen = QPen(transparent_gray, 50)
        self.gantry_bar = QGraphicsLineItem(
            self.gantry_x, 0, self.gantry_x, HEIGHT)
        self.gantry_bar.setPen(gantry_pen)
        self._scene.addItem(self.gantry_bar)

        # Draw gantry position indicator
        circle_radius = 50
        gantry_circle_pen = QPen(transparent_gray, 10)
        self.gantry_position = QGraphicsEllipseItem(
            self.gantry_x - circle_radius,
            self.gantry_y - circle_radius,
            circle_radius * 2,
            circle_radius * 2
        )
        self.gantry_position.setPen(gantry_circle_pen)
        self.gantry_position.setBrush(transparent_gray)
        self._scene.addItem(self.gantry_position)

    def _redraw_gantry(self):
        """Redraw gantry at new position"""
        self._draw_gantry()

    def _load_all_plant_icons(self):
        """Load all plant icons"""
        icons = {}
        try:
            # Get package share directory for icons
            package_share_dir = get_package_share_directory(
                "farmbot_rqt_plugins")
            icons_dir = os.path.join(package_share_dir, "resource", "icons")

            # List of expected plant types based on available icons
            # TODO: get plants in active map
            plant_types = ["Beans", "Beetroot",
                           "Cauliflower", "Lettuce", "Onions"]

            for plant_type in plant_types:
                icon_path = os.path.join(icons_dir, f"{plant_type}.png")
                if os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    # Store original pixmap - we'll scale it based on zoom level
                    icons[plant_type] = pixmap
                    print(f"Loaded icon for {plant_type}")
                else:
                    print(f"Icon not found for {plant_type} at {icon_path}")

        except Exception as e:
            print(f"Error loading plant icons: {e}")

        return icons

    def _draw_plant_icons(self):
        """Draw icons at each plant location, fallback to green circles"""
        if not self.plant_data:
            return

        # Calculate icon size based on zoom level - larger when zoomed out
        if self.zoom_factor <= 0.5:
            # Double size when very zoomed out
            icon_size = int(self.plant_icon_size * 2)
        elif self.zoom_factor <= 1.0:
            # 1.5x size when moderately zoomed out
            icon_size = int(self.plant_icon_size * 1.5)
        else:
            icon_size = self.plant_icon_size  # Normal size when zoomed in

        # Fallback circle properties
        plant_pen = QPen(QColor(34, 139, 34), 2)  # Dark green
        plant_brush = QColor(144, 238, 144)  # Light green
        radius = 8

        for plant_index, plant in enumerate(self.plant_data):
            x, y = plant["x"], plant["y"]
            plant_name = plant["name"]
            canopy_radius = plant["canopy_radius"]

            # Draw transparent canopy radius circle only if toggle is enabled
            if self.show_canopy_radius:
                # Semi-transparent green
                canopy_pen = QPen(QColor(34, 139, 34, 100), 1)
                # Very transparent green fill
                canopy_brush = QColor(34, 139, 34, 30)

                canopy_circle = QGraphicsEllipseItem(
                    x - canopy_radius,
                    y - canopy_radius,
                    canopy_radius * 2,
                    canopy_radius * 2,
                )
                canopy_circle.setPen(canopy_pen)
                canopy_circle.setBrush(canopy_brush)
                self._scene.addItem(canopy_circle)

            # Check if plant has an icon
            if plant_name in self.plant_icons:
                original_icon = self.plant_icons[plant_name]
                # Scale icon based on zoom level
                scaled_icon = original_icon.scaled(
                    icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # Create pixmap item for icon
                icon_item = QGraphicsPixmapItem(scaled_icon)
                # Center the icon on the plant position
                icon_item.setPos(x - scaled_icon.width() / 2,
                                 y - scaled_icon.height() / 2)
                self._scene.addItem(icon_item)
            else:
                # Fallback to green circle
                circle = QGraphicsEllipseItem(
                    x - radius,
                    y - radius,
                    radius * 2,
                    radius * 2,
                )
                circle.setPen(plant_pen)
                circle.setBrush(plant_brush)
                self._scene.addItem(circle)

            text_y_offset = 50  # Distance above plant center
            labels_y = y - text_y_offset

            # Collect label information
            name_text = None
            index_text = None
            name_width = 0
            index_width = 0

            # Create plant name text if enabled
            if self.show_plant_names:
                name_text = QGraphicsTextItem(plant_name)
                name_text.setDefaultTextColor(QColor(255, 255, 255))
                name_text.setFont(QFont("Arial", 18, QFont.Bold))
                name_width = name_text.boundingRect().width()

            # Create plant index text if enabled
            if self.show_plant_indices:
                index_text = QGraphicsTextItem(str(plant_index))
                index_text.setDefaultTextColor(QColor(255, 255, 255))
                index_text.setFont(QFont("Arial", 18, QFont.Bold))
                index_width = index_text.boundingRect().width()

            total_width = name_width + index_width
            start_x = x - total_width / 2
            current_x = start_x

            # Position and add plant name
            if name_text:
                name_text.setPos(current_x, labels_y)

                # Add background for name text
                background_rect = QGraphicsRectItem(name_text.boundingRect())
                background_rect.setPos(current_x, labels_y)
                background_rect.setBrush(QColor(0, 0, 0, 128))
                background_rect.setPen(QPen(Qt.NoPen))
                self._scene.addItem(background_rect)
                self._scene.addItem(name_text)

                current_x += name_width

            # Position and add plant index
            if index_text:
                index_text.setPos(current_x, labels_y)

                # Add background for index text
                index_background_rect = QGraphicsRectItem(
                    index_text.boundingRect())
                index_background_rect.setPos(current_x, labels_y)
                index_background_rect.setBrush(QColor(0, 0, 0, 128))
                index_background_rect.setPen(QPen(Qt.NoPen))
                self._scene.addItem(index_background_rect)
                self._scene.addItem(index_text)

    def _redraw_plants(self):
        """Remove existing plant items and redraw with new zoom sizes"""
        # TODO: fix this
        items_to_remove = []
        for item in self._scene.items():
            if isinstance(item, (QGraphicsPixmapItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsRectItem)):
                # Check if it's a plant item (not a grid line)
                if hasattr(item, 'pen') and isinstance(item, QGraphicsEllipseItem):
                    # Check if it's a plant circle or canopy circle (green color)
                    pen_color = item.pen().color()
                    if pen_color.red() == 34 and pen_color.green() == 139 and pen_color.blue() == 34:
                        items_to_remove.append(item)
                elif isinstance(item, (QGraphicsPixmapItem, QGraphicsTextItem, QGraphicsRectItem)):
                    items_to_remove.append(item)

        for item in items_to_remove:
            self._scene.removeItem(item)

        # Redraw plants with new sizes
        self._draw_plant_icons()

    def _load_active_map(self):
        """Load the active map file"""
        try:
            # Get map directory and file
            map_directory = os.path.join(
                get_package_share_directory("map_handler"), "config"
            )
            map_file = "active_map.yaml"

            # Load map instance
            map_instance = self._load_from_yaml(map_directory, map_file)

            if map_instance:
                self.active_map = map_instance

                # Get map dimensions
                if "map_reference" in map_instance:  # TODO: check this on an recent map
                    self.map_x = map_instance["map_reference"].get("x_len", 0)
                    self.map_y = map_instance["map_reference"].get("y_len", 0)

                # Get plant positions and data
                if (
                    "plant_details" in map_instance
                    and "plants" in map_instance["plant_details"]
                ):
                    plants = map_instance["plant_details"]["plants"]
                    self.plant_positions = []
                    self.plant_data = []
                    for plant_data in plants.values():
                        if plant_data and "position" in plant_data and "identifiers" in plant_data:
                            self.plant_positions.append((
                                plant_data["position"]["x"],
                                plant_data["position"]["y"]
                            ))
                            # Get plant date if available
                            plant_date = plant_data["status"].get(
                                "plant_date", {})
                            date_str = "Unknown"
                            if plant_date:
                                day = plant_date.get("day", "")
                                month = plant_date.get("month", "")
                                year = plant_date.get("year", "")
                                if day and month and year:
                                    date_str = f"{day}/{month}/{year}"

                            # TODO: add plant type for fields
                            self.plant_data.append({
                                "x": plant_data["position"]["x"],
                                "y": plant_data["position"]["y"],
                                "z": plant_data["position"].get("z", 0),
                                "index": plant_data["identifiers"].get("index", "Unknown"),
                                "name": plant_data["identifiers"].get("plant_name", "Unknown"),
                                "canopy_radius": plant_data["plant_details"].get("canopy_radius", 50.0),
                                "max_height": plant_data["plant_details"].get("max_height", 0.0),
                                "plant_radius": plant_data["plant_details"].get("plant_radius", 0.0),
                                "water_quantity": plant_data["plant_details"].get("water_quantity", 0.0),
                                "growth_stage": plant_data["status"].get("growth_stage", "Unknown"),
                                "plant_date": date_str
                            })

                print(f"Active map loaded successfully:")
                print(f"  Map dimensions: {self.map_x} x {self.map_y}")
                print(f"  Plant count: {len(self.plant_positions)}")
            else:
                print("Failed to load active map")

        except Exception as e:
            print(f"Error loading active map: {e}")

    def _load_from_yaml(self, path, file_name):
        """Load YAML file"""
        try:
            file_path = os.path.join(path, file_name)
            if os.path.exists(file_path):
                with open(file_path, "r") as yaml_file:
                    return yaml.safe_load(yaml_file)
            else:
                print(f"Active map file not found: {file_path}")
                return None
        except Exception as e:
            print(f"Error reading YAML file: {e}")
            return None

    def shutdown_plugin(self):
        pass

    def save_settings(self, plugin_settings, instance_settings):
        pass

    def restore_settings(self, plugin_settings, instance_settings):
        pass

    def _zoom_in(self):
        """Zoom in the graphics view"""
        if self.zoom_factor < self.zoom_max:
            self.zoom_factor = min(
                self.zoom_factor + self.zoom_step, self.zoom_max)
            self._apply_zoom()

    def _zoom_out(self):
        """Zoom out the graphics view"""
        # Calculate minimum zoom to keep farmbed width spanning the full view
        view_width = self._graphics_view.viewport().width()
        min_zoom_for_full_width = view_width / WIDTH if view_width > 0 else self.zoom_min

        effective_min_zoom = max(self.zoom_min, min_zoom_for_full_width)

        if self.zoom_factor > effective_min_zoom:
            self.zoom_factor = max(
                self.zoom_factor - self.zoom_step, effective_min_zoom)
            self._apply_zoom()

    def _apply_zoom(self):
        """Apply the current zoom factor to the graphics view"""
        # Reset and apply zoom transform
        self._graphics_view.resetTransform()
        self._graphics_view.scale(self.zoom_factor, self.zoom_factor)

        # Update axis labels to reflect the zoom
        self._update_axis_labels_zoom()

        # Redraw plant icons with new zoom sizes
        self._redraw_plants()

    def _update_axis_labels_zoom(self):
        """Update axis labels to reflect zoom changes"""
        self._top_labels.set_zoom_factor(self.zoom_factor)
        self._left_labels.set_zoom_factor(self.zoom_factor)

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Add any key handling logic here if needed
        pass


class AxisLabelWidget(QWidget):
    """Widget for drawing axis labels"""

    def __init__(self, max_dimension, is_horizontal, padding_right=0, padding_bottom=0):
        super().__init__()
        self.max_dimension = max_dimension
        self.is_horizontal = is_horizontal
        self.scale_factor = 1
        self.zoom_factor = 1.0
        self.offset = 0
        self.padding_right = padding_right
        self.padding_bottom = padding_bottom

        self.label_spacing_mm = 100
        self.label_spacing_pixels = int(
            self.label_spacing_mm * self.scale_factor)

    def set_offset(self, offset):
        """Set the scroll offset for labels"""
        self.offset = offset
        self.update()

    def set_zoom_factor(self, zoom_factor):
        """Set the zoom factor for labels"""
        self.zoom_factor = zoom_factor
        self._update_label_spacing()
        self.update()

    def _update_label_spacing(self):
        """Update label spacing based on zoom factor to prevent overlap"""
        if self.zoom_factor <= 0.6:
            self.label_spacing_mm = 500
        elif self.zoom_factor <= 1.0:
            self.label_spacing_mm = 200
        else:
            self.label_spacing_mm = 100

        self.label_spacing_pixels = int(
            self.label_spacing_mm * self.scale_factor)

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.fillRect(self.rect(), QColor(195, 165, 130))  # Dark brown

        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        if self.is_horizontal:
            # Draw horizontal labels (X-axis)
            widget_width = self.width() - self.padding_right
            for x in range(
                self.label_spacing_pixels,
                self.max_dimension + 1,
                self.label_spacing_pixels,
            ):
                screen_x = (x * self.zoom_factor) + self.offset
                if -20 <= screen_x <= widget_width + self.padding_right:
                    label_text = str(int(x / self.scale_factor))
                    text_width = painter.fontMetrics().width(label_text)
                    text_x = max(
                        0, min(screen_x - text_width // 2,
                               self.width() - text_width)
                    )
                    painter.drawText(int(text_x), 25, label_text)
        else:
            # TODO: fix vertical labels
            # Draw vertical labels (Y-axis)
            widget_height = self.height() - self.padding_bottom
            for y in range(
                self.label_spacing_pixels,
                self.max_dimension + 1,
                self.label_spacing_pixels,
            ):
                screen_y = (y * self.zoom_factor) + self.offset
                if -15 <= screen_y <= widget_height + self.padding_bottom:
                    label_text = str(int(y / self.scale_factor))
                    painter.drawText(10, int(screen_y), label_text)
