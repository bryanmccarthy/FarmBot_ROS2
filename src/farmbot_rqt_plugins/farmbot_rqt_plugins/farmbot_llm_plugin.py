from PyQt5.QtWidgets import QVBoxLayout, QWidget, QTextEdit, QLineEdit, QFrame, QHBoxLayout, QPushButton, QLabel

from rqt_gui_py.plugin import Plugin
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
import yaml
import os
from ament_index_python.packages import get_package_share_directory
from dotenv import load_dotenv

load_dotenv()


@tool
def read_active_map() -> str:
    """Read the active farm map YAML file and return plant information."""
    try:
        # Get map directory and file path same as farmbedtwo_plugin
        map_directory = os.path.join(
            get_package_share_directory("map_handler"), "config"
        )
        map_file_path = os.path.join(map_directory, "active_map.yaml")

        with open(map_file_path, 'r') as file:
            data = yaml.safe_load(file)
        return str(data)
    except Exception as e:
        return f"Error reading active map: {e}"


@tool
def format_command_sequence(command_string: str) -> str:
    """Format the command sequence to display to the user"""
    formatted_command = command_string.strip()
    formatted_output = f"```\n{formatted_command}\n```"

    return formatted_output


# Global reference to plugin instance for the tool
_plugin_instance = None


@tool
def set_proposed_command(command: str) -> str:
    """Set the proposed command for user approval. This will display the command in the approval panel."""
    global _plugin_instance
    if _plugin_instance:
        _plugin_instance.set_proposed_command(command)
        return f"Proposed command set: {command}"
    else:
        return "Error: Plugin instance not available"


@tool
def list_available_commands() -> str:
    """List all available farmbot commands with their details"""

    commands_db = {
        # Movement Commands
        "M": {
            "name": "Move to Position",
            "parameters": ["x", "y", "z"],
            "description": "Move farmbot to absolute coordinates in mm",
            "examples": ["M 100 200 -150"]
        },
        "w": {
            "name": "Move Forward",
            "parameters": [],
            "description": "Move forward by increment amount (add to x-axis)",
            "examples": ["w"]
        },
        "s": {
            "name": "Move Backward",
            "parameters": [],
            "description": "Move backward by increment amount (subtract from x-axis)",
            "examples": ["s"]
        },
        "a": {
            "name": "Move Left",
            "parameters": [],
            "description": "Move left by increment amount (subtract from y-axis)",
            "examples": ["a"]
        },
        "d": {
            "name": "Move Right",
            "parameters": [],
            "description": "Move right by increment amount (add to y-axis)",
            "examples": ["d"]
        },
        "1": {
            "name": "Set Increment 10mm",
            "parameters": [],
            "description": "Set movement increment to 10mm for directional commands",
            "examples": ["1"]
        },
        "2": {
            "name": "Set Increment 100mm",
            "parameters": [],
            "description": "Set movement increment to 100mm for directional commands",
            "examples": ["2"]
        },
        "3": {
            "name": "Set Increment 500mm",
            "parameters": [],
            "description": "Set movement increment to 500mm for directional commands",
            "examples": ["3"]
        },
        "H_0": {
            "name": "Go to Home Position",
            "parameters": [],
            "description": "Move farmbot to home position (0, 0, 0)",
            "examples": ["H_0"]
        },
        "H_1": {
            "name": "Find All Home Positions",
            "parameters": [],
            "description": "Find home positions for all axes (X, Y, Z)",
            "examples": ["H_1"]
        },
        "H_2": {
            "name": "Find Home for Axis",
            "parameters": ["axis"],
            "description": "Find home position for specified axis (X, Y, or Z)",
            "examples": ["H_2 X", "H_2 Y", "H_2 Z"]
        },

        # Emergency and Configuration Commands
        "e": {
            "name": "Emergency Stop",
            "parameters": [],
            "description": "Immediately stop all farmbot operations",
            "examples": ["e"]
        },
        "E": {
            "name": "Emergency Stop Reset",
            "parameters": [],
            "description": "Reset emergency stop state",
            "examples": ["E"]
        },
        "C_0": {
            "name": "Calibrate All Axes",
            "parameters": [],
            "description": "Calibrate all axes (X, Y, Z)",
            "examples": ["C_0"]
        },
        "C_1": {
            "name": "Load Parameter Configuration",
            "parameters": [],
            "description": "Load parameter configuration from file",
            "examples": ["C_1"]
        },
        "C_2": {
            "name": "Invert Encoder Direction",
            "parameters": ["axis"],
            "description": "Invert encoder direction for specified axis",
            "examples": ["C_2 X", "C_2 Y", "C_2 Z"]
        },
        "CONF": {
            "name": "Save Configuration",
            "parameters": [],
            "description": "Save configuration and/or map information",
            "examples": ["CONF"]
        },

        # Tool and Tray Commands
        "T_n_0": {
            "name": "Set Toolhead Location",
            "parameters": ["tool_number"],
            "description": "Set toolhead location for tool n",
            "examples": ["T_1_0", "T_2_0"]
        },
        "T_n_1": {
            "name": "Mount Tool",
            "parameters": ["tool_number"],
            "description": "Mount tool n",
            "examples": ["T_1_1", "T_2_1"]
        },
        "T_n_2": {
            "name": "Unmount Tool",
            "parameters": ["tool_number"],
            "description": "Unmount tool n",
            "examples": ["T_1_2", "T_2_2"]
        },
        "S_n_0": {
            "name": "Set Seed Tray Location",
            "parameters": ["tray_number"],
            "description": "Set seed tray location for tray n",
            "examples": ["S_1_0", "S_2_0"]
        },

        # Plant Commands
        "P_1": {
            "name": "Add Plant",
            "parameters": ["x", "y", "z", "exl_r", "can_r", "water", "max_z", "name", "stage"],
            "description": "Add plant with position and detailed information. x,y,z=position, exl_r=exclusion radius, can_r=canopy radius, water=water quantity, max_z=max height, name=plant name, stage=growth stage",
            "examples": ["P_1 100.0 200.0 -290.0 50.0 30.0 6 Tomato Planning"]
        },
        "P_2": {
            "name": "Remove Plant",
            "parameters": ["plant_index"],
            "description": "Remove plant by index",
            "examples": ["P_2 5"]
        },
        "P_3": {
            "name": "Seed All Plants",
            "parameters": [],
            "description": "Seed all plants in 'Planning' stage",
            "examples": ["P_3"]
        },
        "P_4": {
            "name": "Water All Plants",
            "parameters": [],
            "description": "Water all plants regardless of moisture levels",
            "examples": ["P_4"]
        },
        "P_5": {
            "name": "Water Plants if Dry",
            "parameters": [],
            "description": "Water plants based on moisture levels",
            "examples": ["P_5"]
        },
        "P_9": {
            "name": "Check Soil Moisture",
            "parameters": [],
            "description": "Check moisture levels around plants",
            "examples": ["P_9"]
        },

        # Device Commands
        "D_L_a": {
            "name": "Control LED Strip",
            "parameters": ["a"],
            "description": "Control LED strip (1=on, 0=off)",
            "examples": ["D_L_1", "D_L_0"]
        },
        "D_W_a": {
            "name": "Control Water Pump",
            "parameters": ["a"],
            "description": "Control water pump (1=on, 0=off)",
            "examples": ["D_W_1", "D_W_0"]
        },
        "D_V_a": {
            "name": "Control Vacuum Pump",
            "parameters": ["a"],
            "description": "Control vacuum pump (1=on, 0=off)",
            "examples": ["D_V_1", "D_V_0"]
        },
        "D_C": {
            "name": "Check Tool Mount",
            "parameters": [],
            "description": "Check if tool is mounted",
            "examples": ["D_C"]
        },
        "D_S_C": {
            "name": "Check Soil Sensor",
            "parameters": [],
            "description": "Check soil sensor reading",
            "examples": ["D_S_C"]
        },
        "M_S": {
            "name": "Move Servo",
            "parameters": ["angle"],
            "description": "Move servo to specified angle",
            "examples": ["M_S 90", "M_S 180"]
        },

        # Vision Commands
        "I_0": {
            "name": "Calibrate Camera",
            "parameters": [],
            "description": "Calibrate camera",
            "examples": ["I_0"]
        },
        "I_1": {
            "name": "Take Picture and Stitch",
            "parameters": [],
            "description": "Take picture and stitch to panorama",
            "examples": ["I_1"]
        },
        "I_2": {
            "name": "Create Panorama Sequence",
            "parameters": [],
            "description": "Create panorama sequence",
            "examples": ["I_2"]
        },
        "I_3": {
            "name": "Mosaic Image Stitching",
            "parameters": [],
            "description": "Mosaic image stitching (Work in Progress)",
            "examples": ["I_3"]
        },
        "I_4": {
            "name": "Detect Weeds",
            "parameters": [],
            "description": "Detect weeds in the garden",
            "examples": ["I_4"]
        }
    }

    # Format output
    result = "Available Farmbot Commands:\n\n"

    for cmd_code, cmd_info in commands_db.items():
        result += f"**{cmd_code}** - {cmd_info['name']}\n"
        result += f"  Description: {cmd_info['description']}\n"
        if cmd_info['parameters']:
            result += f"  Parameters: {', '.join(cmd_info['parameters'])}\n"
        result += f"  Example: {cmd_info['examples'][0]}\n\n"

    return result


class FarmbotLLMPlugin(Plugin):
    def __init__(self, context):
        super(FarmbotLLMPlugin, self).__init__(context)
        self.setObjectName("FarmbotLLMPlugin")

        # Set global reference for tools
        global _plugin_instance
        _plugin_instance = self

        self._widget = QWidget()

        layout = QVBoxLayout()

        # Chat display area
        self.chat_display = QTextEdit()

        # Initialize LangChain agent executor
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = api_key

            self.model = init_chat_model("gpt-4.1", model_provider="openai")
            self.tools = [read_active_map,
                          list_available_commands, format_command_sequence, set_proposed_command]

            # TODO: move to file
            system_prompt = """
                You are a farmbot assistant that can:
                - Read farm data to answer questions about plants
                - Analyze plant locations and growing conditions
                - Generate appropriate command sequences

                - You can list all available commands with list_available_commands
                - you can read active state in active_map.yaml
                - Use format_command_sequence to format command outputs
                - Use set_proposed_command to propose commands for user approval

                - If the user gives farmbot commands in natural language first use list_available_commands to see available commands
                - Check the active map for current state for any commands that require knowledge
                - When providing command sequences, use set_proposed_command to propose them for user approval instead of format_command_sequence
    
                ## Example 1: Basic Movement
                **Input:** "Move to position 100, 200, -150"
                **Process:** Use set_proposed_command("M 100 200 -150")
                **Output:** Command is proposed for user approval

                ## Example 2: Water All Plants
                **Input:** "Water all the plants"
                **Process:** Use set_proposed_command("P_4")
                **Output:** Command is proposed for user approval

                ## Example 3: Check Soil and Water if Needed
                **Input:** "Check soil moisture and water any dry plants"
                **Process:** Use set_proposed_command("P_9\nP_5")
                **Output:** Command is proposed for user approval

                ## Example 4: Take Photos
                **Input:** "Take a picture of the whole garden"
                **Process:** Use set_proposed_command("I_2")
                **Output:** Command is proposed for user approval

                ## Example 5: Incremental Movement
                **Input:** "Move forward 100mm then right 200mm"
                **Process:** Use set_proposed_command("2\nw\n2\nd\nd")
                **Output:** Command is proposed for user approval

                ## Example 6: Incremental Movement 2
                **Input:** "Move backwards one meter"
                **Process:** Use set_proposed_command("3\ns\ns")
                **Output:** Command is proposed for user approval

                ## Example 7: Go Home
                **Input:** "Go to home position"
                **Process:** Use set_proposed_command("H_0")
                **Output:** Command is proposed for user approval

                ## Example 8: Emergency Stop
                **Input:** "Stop everything immediately"
                **Process:** Use set_proposed_command("e")
                **Output:** Command is proposed for user approval
            """

            self.prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{chat_history}"),
                ("user", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])

            agent = create_openai_tools_agent(
                self.model, self.tools, self.prompt)
            self.agent_executor = AgentExecutor(
                agent=agent, tools=self.tools, verbose=True)
            self.chat_history = []

        except Exception as e:
            print(f"Error initializing LangChain agent: {e}")
            self.agent_executor = None
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
            }
        """)
        layout.addWidget(self.chat_display)

        # Panel widget between chat and input
        self.panel_widget = QFrame()
        self.panel_widget.setFrameStyle(QFrame.Box)
        self.panel_widget.setMinimumHeight(100)
        self.panel_widget.setMaximumHeight(200)
        self.panel_widget.setStyleSheet("""
            QFrame {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: #f9f9f9;
            }
        """)

        # Panel layout
        panel_layout = QVBoxLayout()

        # Command display label
        self.command_label = QLabel("No command proposed")
        self.command_label.setStyleSheet("""
            QLabel {
                font-family: monospace;
                font-size: 14px;
                padding: 10px;
                background-color: #ffffff;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)
        panel_layout.addWidget(self.command_label)

        # Buttons layout
        button_layout = QHBoxLayout()

        self.accept_button = QPushButton("Accept")
        self.accept_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #999;
            }
        """)
        self.accept_button.clicked.connect(self._accept_command)
        self.accept_button.setEnabled(False)

        self.reject_button = QPushButton("Reject")
        self.reject_button.setStyleSheet("""
            QPushButton {
                border: 2px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #999;
            }
        """)
        self.reject_button.clicked.connect(self._reject_command)
        self.reject_button.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.reject_button)
        button_layout.addStretch()

        panel_layout.addLayout(button_layout)
        self.panel_widget.setLayout(panel_layout)

        # Initialize proposed command state and hide panel initially
        self.proposed_command = None
        self.panel_widget.setVisible(False)

        layout.addWidget(self.panel_widget)

        # Input box
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type your message...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 5px;
                font-size: 16px;
            }
            QLineEdit:focus {
                outline: none;
                border: 2px solid #ddd;
            }
        """)
        self.input_box.returnPressed.connect(self._send_message)
        layout.addWidget(self.input_box)

        self._widget.setLayout(layout)
        context.add_widget(self._widget)

    def set_proposed_command(self, command):
        """Set the proposed command in the UI"""
        self.proposed_command = command
        self.command_label.setText(command)
        self.accept_button.setEnabled(True)
        self.reject_button.setEnabled(True)
        self.panel_widget.setVisible(True)

    def _accept_command(self):
        """Handle accept button click"""
        if self.proposed_command:
            self.chat_display.append(
                f"<span>✓ Command accepted: {self.proposed_command}</span>")
            self._clear_proposed_command()

    def _reject_command(self):
        """Handle reject button click"""
        if self.proposed_command:
            self.chat_display.append(
                f"<span>✗ Command rejected: {self.proposed_command}</span>")
            self._clear_proposed_command()

    def _clear_proposed_command(self):
        """Clear the proposed command state"""
        self.proposed_command = None
        self.command_label.setText("No command proposed")
        self.accept_button.setEnabled(False)
        self.reject_button.setEnabled(False)
        self.panel_widget.setVisible(False)

    def _send_message(self):
        message = self.input_box.text()
        if message:
            # Display user message
            self.chat_display.append(
                f"<span style='color: #555;'>• {message}</span>")
            self.input_box.clear()

            if self.agent_executor:
                try:
                    response = self.agent_executor.invoke({
                        "input": message,
                        "chat_history": self.chat_history
                    })

                    # Add to history
                    self.chat_history.extend([
                        HumanMessage(content=message),
                        AIMessage(content=response['output'])
                    ])

                    # Display response
                    self.chat_display.append(f"• {response['output']}")

                except Exception as e:
                    self.chat_display.append(f"Error: {e}")
            else:
                self.chat_display.append("Agent not initialized")

    def shutdown_plugin(self):
        pass

    def save_settings(self, plugin_settings, instance_settings):
        pass

    def restore_settings(self, plugin_settings, instance_settings):
        pass
