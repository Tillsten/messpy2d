import time
import os
import sys
from ctypes import *
from typing import Optional


class ThorlabsKDC101:
    """
    A class to control Thorlabs KDC101 motor controller.

    This class provides a clean interface to control a Thorlabs KDC101 DC servo motor
    controller through the Kinesis API.
    """

    def __init__(
        self,
        serial_number: str,
        steps_per_rev: float = 1919.64186,
        gbox_ratio: float = 1.0,
        pitch: float = 1.0,
        polling_rate: int = 200,
        use_simulation: bool = False,
    ):
        """
        Initialize the KDC101 controller.

        Args:
            serial_number: The serial number of the device (e.g., "27500125")
            steps_per_rev: Steps per revolution for the motor (default for PRM1-Z8)
            gbox_ratio: Gearbox ratio (default 1.0)
            pitch: Pitch value (default 1.0)
            polling_rate: Polling rate in ms (default 200)
            use_simulation: Whether to use simulation mode
        """
        self.serial_number = serial_number
        self.serial_num_c = c_char_p(serial_number.encode())
        self.steps_per_rev = c_double(steps_per_rev)
        self.gbox_ratio = c_double(gbox_ratio)
        self.pitch = c_double(pitch)
        self.polling_rate = polling_rate
        self.use_simulation = use_simulation

        self.lib: Optional[CDLL] = None
        self.is_connected = False
        self.is_homed = False

        self._load_library()

    def _load_library(self):
        """Load the Thorlabs Kinesis DLL."""
        try:
            if sys.version_info < (3, 8):
                os.chdir(r"C:\Program Files\Thorlabs\Kinesis")
            else:
                os.add_dll_directory(r"C:\Program Files\Thorlabs\Kinesis")

            self.lib = cdll.LoadLibrary("Thorlabs.MotionControl.KCube.DCServo.dll")

            if self.use_simulation:
                self.lib.TLI_InitializeSimulations()

        except Exception as e:
            raise RuntimeError(f"Failed to load Thorlabs library: {e}")

    def connect(self) -> bool:
        """
        Connect to the device.

        Returns:
            True if connection successful, False otherwise
        """
        if self.is_connected:
            return True

        try:
            if self.lib.TLI_BuildDeviceList() == 0:
                result = self.lib.CC_Open(self.serial_num_c)
                if result == 0:
                    self.lib.CC_StartPolling(
                        self.serial_num_c, c_int(self.polling_rate)
                    )
                    self._setup_motor_parameters()
                    self.is_connected = True
                    return True
            return False
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def _setup_motor_parameters(self):
        """Set up motor parameters for unit conversion."""
        self.lib.CC_SetMotorParamsExt(
            self.serial_num_c, self.steps_per_rev, self.gbox_ratio, self.pitch
        )

    def home(self, wait: bool = True) -> bool:
        """
        Home the device.

        Args:
            wait: Whether to wait for homing to complete

        Returns:
            True if homing initiated successfully
        """
        if not self.is_connected:
            raise RuntimeError("Device not connected. Call connect() first.")

        try:
            result = self.lib.CC_Home(self.serial_num_c)
            if wait:
                time.sleep(1)  # Wait for homing to complete
            self.is_homed = True
            return result == 0
        except Exception as e:
            print(f"Homing failed: {e}")
            return False

    def get_position(self) -> float:
        """
        Get the current position in real units.

        Returns:
            Current position as float
        """
        if not self.is_connected:
            raise RuntimeError("Device not connected. Call connect() first.")

        try:
            self.lib.CC_RequestPosition(self.serial_num_c)
            time.sleep(0.2)
            dev_pos = c_int(self.lib.CC_GetPosition(self.serial_num_c))

            real_pos = c_double()
            self.lib.CC_GetRealValueFromDeviceUnit(
                self.serial_num_c, dev_pos, byref(real_pos), 0
            )

            return real_pos.value
        except Exception as e:
            raise RuntimeError(f"Failed to get position: {e}")

    def move_absolute(self, position: float, wait: bool = True) -> bool:
        """
        Move to an absolute position.

        Args:
            position: Target position in real units
            wait: Whether to wait briefly after initiating move

        Returns:
            True if move initiated successfully
        """
        if not self.is_connected:
            raise RuntimeError("Device not connected. Call connect() first.")

        try:
            new_pos_real = c_double(position)
            new_pos_dev = c_int()

            self.lib.CC_GetDeviceUnitFromRealValue(
                self.serial_num_c, new_pos_real, byref(new_pos_dev), 0
            )

            self.lib.CC_SetMoveAbsolutePosition(self.serial_num_c, new_pos_dev)
            if wait:
                time.sleep(0.25)

            result = self.lib.CC_MoveAbsolute(self.serial_num_c)
            return result == 0
        except Exception as e:
            print(f"Move failed: {e}")
            return False

    def move_relative(self, displacement: float, wait: bool = True) -> bool:
        """
        Move by a relative displacement.

        Args:
            displacement: Relative displacement in real units
            wait: Whether to wait briefly after initiating move

        Returns:
            True if move initiated successfully
        """
        current_pos = self.get_position()
        return self.move_absolute(current_pos + displacement, wait)

    def disconnect(self):
        """Disconnect from the device."""
        if self.is_connected:
            try:
                self.lib.CC_Close(self.serial_num_c)
                self.is_connected = False
                self.is_homed = False
            except Exception as e:
                print(f"Disconnect failed: {e}")

    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise RuntimeError("Failed to connect to device")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        if self.use_simulation and self.lib:
            try:
                self.lib.TLI_UninitializeSimulations()
            except:
                pass


# Example usage function (keeping for compatibility)
def main():
    """
    Example usage of the ThorlabsKDC101 class.
    """

    # Using context manager (recommended)
    with ThorlabsKDC101("27266697") as stage:
        # Home the device
        if stage.home():
            print(f"Position after homing: {stage.get_position()}")

        # Move to a new position
        target_position = 5.0
        if stage.move_absolute(target_position):
            print(f"Moving to position: {target_position}")
            time.sleep(1)  # Wait for move to complete
            print(f"Current position: {stage.get_position()}")

    # Alternative usage without context manager
    # stage = ThorlabsKDC101("27500125")
    # stage.connect()
    # stage.home()
    # stage.move_absolute(5.0)
    # stage.disconnect()


from MessPy.Instruments.interfaces import IRotationStage
from attr import dataclass


@dataclass
class TLRotStage(IRotationStage):
    stage: ThorlabsKDC101 = ThorlabsKDC101("27266697")
    target: float = float("inf")

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.stage.connect()
        self.target = self.get_degrees()

    def get_degrees(self) -> float:

        pos = self.stage.get_position()
        self.sigDegreesChanged.emit(pos)
        return pos

    def check_moving(self):
        from PySide6.QtCore import QTimer

        if moving := self.is_moving():
            QTimer.singleShot(200, self.check_moving)
        else:
            self.sigMovementCompleted.emit()
        self.sigDegreesChanged.emit(self.get_degrees())

    def set_degrees(self, deg: float):
        self.target = deg
        self.stage.move_absolute(deg)
        from PySide6.QtCore import QTimer
        self._checker = QTimer.singleShot(100, self.check_moving)

    def is_moving(self) -> bool:
        return abs(self.get_degrees() - self.target) > 0.01


if __name__ == "__main__":
    main()
