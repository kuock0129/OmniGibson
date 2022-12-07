"""
Helper classes and functions for streamlining user interactions
"""

import numpy as np
import sys
from collections import OrderedDict
import omnigibson as og
from omnigibson.macros import gm
import omnigibson.utils.transform_utils as T
import omni
import carb
import random


class KeyboardEventHandler:
    """
    Simple singleton class for handing keyboard events
    """
    # Global keyboard callbacks
    KEYBOARD_CALLBACKS = OrderedDict()

    # ID assigned to meta callback method for this class
    _CALLBACK_ID = None

    def __init__(self):
        raise ValueError("Cannot create an instance of keyboard event handler!")

    @classmethod
    def initialize(cls):
        """
        Hook up a meta function callback to the omni backend
        """
        appwindow = omni.appwindow.get_default_app_window()
        input_interface = carb.input.acquire_input_interface()
        keyboard = appwindow.get_keyboard()
        cls._CALLBACK_ID = input_interface.subscribe_to_keyboard_events(keyboard, cls._meta_callback)

    @classmethod
    def reset(cls):
        """
        Resets this callback interface by removing all current callback functions
        """
        appwindow = omni.appwindow.get_default_app_window()
        input_interface = carb.input.acquire_input_interface()
        keyboard = appwindow.get_keyboard()
        input_interface.unsubscribe_to_keyboard_events(keyboard, cls._CALLBACK_ID)
        cls.KEYBOARD_CALLBACKS = OrderedDict()
        cls._CALLBACK_ID = None

    @classmethod
    def add_keyboard_callback(cls, key, callback_fn):
        """
        Registers a keyboard callback function with omni, mapping a keypress from @key to run the callback_function
        @callback_fn

        Args:
            key (carb.input.KeyboardInput): key to associate with the callback
            callback_fn (function): Callback function to call if the key @key is pressed or repeated. Note that this
                function's signature should be:

                callback_fn() --> None
        """
        # Initialize the interface if not initialized yet
        if cls._CALLBACK_ID is None:
            cls.initialize()
        # Add the callback
        cls.KEYBOARD_CALLBACKS[key] = callback_fn

    @classmethod
    def _meta_callback(cls, event, *args, **kwargs):
        """
        Meta callback function that is hooked up to omni's backend
        """
        # Check if we've received a key press or repeat
        if event.type == carb.input.KeyboardEventType.KEY_PRESS \
                or event.type == carb.input.KeyboardEventType.KEY_REPEAT:
            # Run the specific callback
            cls.KEYBOARD_CALLBACKS.get(event.input, lambda: None)()

        # Always return True
        return True


def disclaimer(msg):
    """
    Prints a disclaimer message, i.e.: "We know this doesn't work; it's an omni issue; we expect it to be fixed in the
    next release!
    """
    if gm.SHOW_DISCLAIMERS:
        print("****** DISCLAIMER ******")
        print("Isaac Sim / Omniverse has some significant limitations and bugs in its current release.")
        print("This message has popped up because a potential feature in OmniGibson relies upon a feature in Omniverse that "
              "is yet to be released publically. Currently, the expected behavior may not be fully functional, but "
              "should be resolved by the next Isaac Sim release.")
        print(f"Exact Limitation: {msg}")
        print("************************")


def choose_from_options(options, name, random_selection=False):
    """
    Prints out options from a list, and returns the requested option.

    :param options: dict or Array, options to choose from. If dict, the value entries are assumed to be docstrings
        explaining the individual options
    :param name: str, name of the options
    :param random_selection: bool, if the selection is random (for automatic demo execution). Default False

    :return str: Requested option
    """
    # Select robot
    print("\nHere is a list of available {}s:\n".format(name))

    for k, option in enumerate(options):
        docstring = ": {}".format(options[option]) if isinstance(options, dict) else ""
        print("[{}] {}{}".format(k + 1, option, docstring))
    print()

    if not random_selection:
        try:
            s = input("Choose a {} (enter a number from 1 to {}): ".format(name, len(options)))
            # parse input into a number within range
            k = min(max(int(s), 1), len(options)) - 1
        except:
            k = 0
            print("Input is not valid. Use {} by default.".format(list(options)[k]))
    else:
        k = random.choice(range(len(options)))

    # Return requested option
    return list(options)[k]


class CameraMover:
    """
    A helper class for manipulating a camera via the keyboard. Utilizes carb keyboard callbacks to move
    the camera around.

    Args:
        cam (VisionSensor): The camera vision sensor to manipulate via the keyboard
        delta (float): Change (m) per keypress when moving the camera
    """
    def __init__(self, cam, delta=0.25):
        self.cam = cam
        self.delta = delta

        self._appwindow = omni.appwindow.get_default_app_window()
        self._input = carb.input.acquire_input_interface()
        self._keyboard = self._appwindow.get_keyboard()
        self._sub_keyboard = self._input.subscribe_to_keyboard_events(self._keyboard, self._sub_keyboard_event)

    def print_info(self):
        """
        Prints keyboard command info out to the user
        """
        print("*" * 40)
        print("CameraMover! Commands:")
        print()
        print(f"\t Right Click + Drag: Rotate camera")
        print(f"\t W / S : Move camera forward / backward")
        print(f"\t A / D : Move camera left / right")
        print(f"\t T / G : Move camera up / down")
        print(f"\t P : Print current camera pose")

    def print_cam_pose(self):
        """
        Prints out the camera pose as (position, quaternion) in the world frame
        """
        print(f"cam pose: {self.cam.get_position_orientation()}")

    def set_delta(self, delta):
        """
        Sets the delta value (how much the camera moves with each keypress) for this CameraMover

        Args:
            delta (float): Change (m) per keypress when moving the camera
        """
        self.delta = delta

    def set_cam(self, cam):
        """
        Sets the active camera sensor for this CameraMover

        Args:
            cam (VisionSensor): The camera vision sensor to manipulate via the keyboard
        """
        self.cam = cam

    @property
    def input_to_function(self):
        """
        Returns:
            dict: Mapping from relevant keypresses to corresponding function call to use
        """
        return {
            carb.input.KeyboardInput.P: lambda: self.print_cam_pose(),
        }

    @property
    def input_to_command(self):
        """
        Returns:
            dict: Mapping from relevant keypresses to corresponding delta command to apply to the camera pose
        """
        return {
            carb.input.KeyboardInput.D: np.array([self.delta, 0, 0]),
            carb.input.KeyboardInput.A: np.array([-self.delta, 0, 0]),
            carb.input.KeyboardInput.W: np.array([0, 0, -self.delta]),
            carb.input.KeyboardInput.S: np.array([0, 0, self.delta]),
            carb.input.KeyboardInput.T: np.array([0, self.delta, 0]),
            carb.input.KeyboardInput.G: np.array([0, -self.delta, 0]),
        }

    def _sub_keyboard_event(self, event, *args, **kwargs):
        """
        Handle keyboard events. Note: The signature is pulled directly from omni.

        Args:
            event (int): keyboard event type
        """
        if event.type == carb.input.KeyboardEventType.KEY_PRESS \
                or event.type == carb.input.KeyboardEventType.KEY_REPEAT:

            if event.type == carb.input.KeyboardEventType.KEY_PRESS and event.input in self.input_to_function:
                self.input_to_function[event.input]()

            else:
                command = self.input_to_command.get(event.input, None)

                if command is not None:
                    # Convert to world frame to move the camera
                    transform = T.quat2mat(self.cam.get_orientation())
                    delta_pos_global = transform @ command
                    self.cam.set_position(self.cam.get_position() + delta_pos_global)

        return True


class KeyboardRobotController:
    """
    Simple class for controlling OmniGibson robots using keyboard commands
    """

    def __init__(self, robot):
        """
        :param robot: BaseRobot, robot to control
        """
        # Store relevant info from robot
        self.robot = robot
        self.action_dim = robot.action_dim
        self.controller_info = OrderedDict()
        idx = 0
        for name, controller in robot._controllers.items():
            self.controller_info[name] = {
                "name": type(controller).__name__,
                "start_idx": idx,
                "dofs": controller.dof_idx,
                "command_dim": controller.command_dim,
            }
            idx += controller.command_dim

        # Other persistent variables we need to keep track of
        self.joint_names = [name for name in robot.joints.keys()]  # Ordered list of joint names belonging to the robot
        self.joint_command_idx = None   # Indices of joints being directly controlled in the action array
        self.joint_control_idx = None  # Indices of joints being directly controlled in the actual joint array
        self.active_joint_command_idx_idx = 0   # Which index within the joint_command_idx variable is being controlled by the user
        self.current_joint = -1  # Active joint being controlled for joint control
        self.ik_arms = []               # List of arm controller names to be controlled by IK
        self.active_arm_idx = 0         # Which index within self.ik_arms is actively being controlled (only relevant for IK)
        self.binary_grippers = []           # Grippers being controlled using multi-finger binary controller
        self.active_gripper_idx = 0     # Which index within self.binary_grippers is actively being controlled
        self.gripper_direction = None  # Flips between -1 and 1, per arm controlled by multi-finger binary control
        self.persistent_gripper_action = None  # Persistent gripper commands, per arm controlled by multi-finger binary control
        # i.e.: if using binary gripper control and when no keypress is active, the gripper action should still the last executed gripper action
        self.keypress_mapping = None    # Maps omni keybindings to information for controlling various parts of the robot
        self.current_keypress = None    # Current key that is being pressed
        self.active_action = None       # Current action information based on the current keypress
        self.toggling_gripper = False   # Whether we should toggle the gripper during the next action

        # Populate the keypress mapping dictionary
        self.populate_keypress_mapping()

        # Register the keyboard callback function
        self.register_keyboard_handler()

    def register_keyboard_handler(self):
        """
        Sets up the keyboard callback functionality with omniverse
        """
        appwindow = omni.appwindow.get_default_app_window()
        input_interface = carb.input.acquire_input_interface()
        keyboard = appwindow.get_keyboard()
        sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, self.keyboard_event_handler)

    def generate_ik_keypress_mapping(self, controller_info):
        """
        Generates a dictionary for keypress mappings for IK control, based on the inputted @controller_info

        Args:
            controller_info (dict): Dictionary of controller information for the specific robot arm to control
                with IK

        Returns:
            dict: Populated keypress mappings for IK to control the specified controller
        """
        mapping = {}

        mapping[carb.input.KeyboardInput.UP] = {"idx": controller_info["start_idx"] + 0, "val": 0.5}
        mapping[carb.input.KeyboardInput.DOWN] = {"idx": controller_info["start_idx"] + 0, "val": -0.5}
        mapping[carb.input.KeyboardInput.RIGHT] = {"idx": controller_info["start_idx"] + 1, "val": -0.5}
        mapping[carb.input.KeyboardInput.LEFT] = {"idx": controller_info["start_idx"] + 1, "val": 0.5}
        mapping[carb.input.KeyboardInput.P] = {"idx": controller_info["start_idx"] + 2, "val": 0.5}
        mapping[carb.input.KeyboardInput.SEMICOLON] = {"idx": controller_info["start_idx"] + 2, "val": -0.5}
        mapping[carb.input.KeyboardInput.N] = {"idx": controller_info["start_idx"] + 3, "val": 0.5}
        mapping[carb.input.KeyboardInput.B] = {"idx": controller_info["start_idx"] + 3, "val": -0.5}
        mapping[carb.input.KeyboardInput.O] = {"idx": controller_info["start_idx"] + 4, "val": 0.5}
        mapping[carb.input.KeyboardInput.U] = {"idx": controller_info["start_idx"] + 4, "val": -0.5}
        mapping[carb.input.KeyboardInput.V] = {"idx": controller_info["start_idx"] + 5, "val": 0.5}
        mapping[carb.input.KeyboardInput.C] = {"idx": controller_info["start_idx"] + 5, "val": -0.5}

        return mapping

    def populate_keypress_mapping(self):
        """
        Populates the mapping @self.keypress_mapping, which maps keypresses to action info:

            keypress:
                idx: <int>
                val: <float>
        """
        self.keypress_mapping = {}
        self.joint_command_idx = []
        self.joint_control_idx = []
        self.gripper_direction = {}
        self.persistent_gripper_action = {}

        # Add mapping for joint control directions (no index because these are inferred at runtime)
        self.keypress_mapping[carb.input.KeyboardInput.RIGHT_BRACKET] = {"idx": None, "val": 0.1}
        self.keypress_mapping[carb.input.KeyboardInput.LEFT_BRACKET] = {"idx": None, "val": -0.1}

        # Iterate over all controller info and populate mapping
        for component, info in self.controller_info.items():
            if info["name"] == "JointController":
                for i in range(info["command_dim"]):
                    cmd_idx = info["start_idx"] + i
                    self.joint_command_idx.append(cmd_idx)
                self.joint_control_idx += info["dofs"].tolist()
            elif info["name"] == "DifferentialDriveController":
                self.keypress_mapping[carb.input.KeyboardInput.I] = {"idx": info["start_idx"] + 0, "val": 0.4}
                self.keypress_mapping[carb.input.KeyboardInput.K] = {"idx": info["start_idx"] + 0, "val": -0.4}
                self.keypress_mapping[carb.input.KeyboardInput.L] = {"idx": info["start_idx"] + 1, "val": -0.2}
                self.keypress_mapping[carb.input.KeyboardInput.J] = {"idx": info["start_idx"] + 1, "val": 0.2}
            elif info["name"] == "InverseKinematicsController":
                self.ik_arms.append(component)
                self.keypress_mapping.update(self.generate_ik_keypress_mapping(controller_info=info))
            elif info["name"] == "MultiFingerGripperController":
                if info["command_dim"] > 1:
                    for i in range(info["command_dim"]):
                        cmd_idx = info["start_idx"] + i
                        self.joint_command_idx.append(cmd_idx)
                    self.joint_control_idx += info["dofs"].tolist()
                else:
                    self.keypress_mapping[carb.input.KeyboardInput.T] = {"idx": info["start_idx"], "val": 1.0}
                    self.gripper_direction[component] = 1.0
                    self.persistent_gripper_action[component] = 1.0
                    self.binary_grippers.append(component)
            elif info["name"] == "NullJointController":
                # We won't send actions if using a null gripper controller
                self.keypress_mapping[carb.input.KeyboardInput.T] = {"idx": None, "val": None}
            else:
                raise ValueError("Unknown controller name received: {}".format(info["name"]))

    def keyboard_event_handler(self, event, *args, **kwargs):
        # Check if we've received a key press or repeat
        if event.type == carb.input.KeyboardEventType.KEY_PRESS \
                or event.type == carb.input.KeyboardEventType.KEY_REPEAT:

            # Handle special cases
            if event.input in {carb.input.KeyboardInput.KEY_1, carb.input.KeyboardInput.KEY_2} and len(self.joint_control_idx) > 1:
                # Update joint and print out new joint being controlled
                self.active_joint_command_idx_idx = max(0, self.active_joint_command_idx_idx - 1) \
                    if event.input == carb.input.KeyboardInput.KEY_1 \
                    else min(len(self.joint_control_idx) - 1, self.active_joint_command_idx_idx + 1)
                print(f"Now controlling joint {self.joint_names[self.joint_control_idx[self.active_joint_command_idx_idx]]}")

            elif event.input in {carb.input.KeyboardInput.KEY_3, carb.input.KeyboardInput.KEY_4} and len(self.ik_arms) > 1:
                # Update arm, update keypress mapping, and print out new arm being controlled
                self.active_arm_idx = max(0, self.active_arm_idx - 1) \
                    if event.input == carb.input.KeyboardInput.KEY_3 \
                    else min(len(self.ik_arms) - 1, self.active_arm_idx + 1)
                new_arm = self.ik_arms[self.active_arm_idx]
                self.keypress_mapping.update(self.generate_ik_keypress_mapping(self.controller_info[new_arm]))
                print(f"Now controlling arm {new_arm} with IK")

            elif event.input in {carb.input.KeyboardInput.KEY_5, carb.input.KeyboardInput.KEY_6} and len(self.binary_grippers) > 1:
                # Update gripper, update keypress mapping, and print out new gripper being controlled
                self.active_gripper_idx = max(0, self.active_gripper_idx - 1) \
                    if event.input == carb.input.KeyboardInput.KEY_5 \
                    else min(len(self.binary_grippers) - 1, self.active_gripper_idx + 1)
                print(f"Now controlling gripper {self.binary_grippers[self.active_gripper_idx]} with binary toggling")

            elif event.input == carb.input.KeyboardInput.R:
                # Render the sensors from the robot's camera and lidar
                self.robot.visualize_sensors()

            elif event.input == carb.input.KeyboardInput.ESCAPE:
                # Terminate immediately
                og.shutdown()

            else:
                # Handle all other actions and update accordingly
                self.active_action = self.keypress_mapping.get(event.input, None)

            if event.type == carb.input.KeyboardEventType.KEY_PRESS:
                # Store the current keypress
                self.current_keypress = event.input

                # Also store whether we pressed the key for toggling gripper actions
                if event.input == carb.input.KeyboardInput.T:
                    self.toggling_gripper = True

        # If we release a key, clear the active action and keypress
        elif event.type == carb.input.KeyboardEventType.KEY_RELEASE:
            self.active_action = None
            self.current_keypress = None

        # Callback always needs to return True
        return True

    def get_random_action(self):
        """
        :return Array: Generated random action vector (normalized)
        """
        return np.random.uniform(-1, 1, self.action_dim)

    def get_teleop_action(self):
        """
        :return Array: Generated action vector based on received user inputs from the keyboard
        """
        action = np.zeros(self.action_dim)

        # Handle the action if any key is actively being pressed
        if self.active_action is not None:
            idx, val = self.active_action["idx"], self.active_action["val"]

            # Only handle the action if the value is specified
            if val is not None:
                # If there is no index, the user is controlling a joint with "[" and "]"
                if idx is None:
                    idx = self.joint_command_idx[self.active_joint_command_idx_idx]

                # Set the action
                action[idx] = val

        # Possibly set the persistent gripper action
        if len(self.binary_grippers) > 0 and self.keypress_mapping[carb.input.KeyboardInput.T]["val"] is not None:

            for i, binary_gripper in enumerate(self.binary_grippers):
                # Possibly update the stored value if the toggle gripper key has been pressed and
                # it's the active gripper being controlled
                if self.toggling_gripper and i == self.active_gripper_idx:
                    # We toggle the gripper direction or this gripper
                    self.gripper_direction[binary_gripper] *= -1.0
                    self.persistent_gripper_action[binary_gripper] = \
                        self.keypress_mapping[carb.input.KeyboardInput.T]["val"] * self.gripper_direction[binary_gripper]

                    # Clear the toggling gripper flag
                    self.toggling_gripper = False

                # Set the persistent action
                action[self.controller_info[binary_gripper]["start_idx"]] = self.persistent_gripper_action[binary_gripper]

        # Print out the user what is being pressed / controlled
        sys.stdout.write("\033[K")
        keypress_str = self.current_keypress.__str__().split(".")[-1]
        print("Pressed {}. Action: {}".format(keypress_str, action))
        sys.stdout.write("\033[F")

        # Return action
        return action

    @staticmethod
    def print_keyboard_teleop_info():
        """
        Prints out relevant information for teleop controlling a robot
        """

        def print_command(char, info):
            char += " " * (10 - len(char))
            print("{}\t{}".format(char, info))

        print()
        print("*" * 30)
        print("Controlling the Robot Using the Keyboard")
        print("*" * 30)
        print()
        print("Joint Control")
        print_command("1, 2", "decrement / increment the joint to control")
        print_command("[, ]", "move the joint backwards, forwards, respectively")
        print()
        print("Differential Drive Control")
        print_command("i, k", "turn left, right")
        print_command("l, j", "move forward, backwards")
        print()
        print("Inverse Kinematics Control")
        print_command("3, 4", "toggle between the different arm(s) to control")
        print_command(u"\u2190, \u2192", "translate arm eef along x-axis")
        print_command(u"\u2191, \u2193", "translate arm eef along y-axis")
        print_command("p, ;", "translate arm eef along z-axis")
        print_command("n, b", "rotate arm eef about x-axis")
        print_command("o, u", "rotate arm eef about y-axis")
        print_command("v, c", "rotate arm eef about z-axis")
        print()
        print("Boolean Gripper Control")
        print_command("5, 6", "toggle between the different gripper(s) using binary control")
        print_command("t", "toggle gripper (open/close)")
        print()
        print("Sensor Rendering")
        print_command("r", "render the onboard sensors (RGB, Depth, Normals, Instance Segmentation, Occupancy Map")
        print()
        print("*" * 30)
        print()
