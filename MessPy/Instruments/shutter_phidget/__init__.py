import time

from attr import dataclass, field
from Phidget22.Devices.RCServo import RCServo

from MessPy.Instruments.interfaces import IShutter


@dataclass(kw_only=True)
class PhidgetShutter(IShutter):
	name: str = 'Phidget Shutter'
	pos_dict: dict = {'close': 90, 'open': 120 }
	_servo: RCServo = field()
	_is_open: bool = field()

	@_servo.default
	def _init_servo(self) -> RCServo:
		servo = RCServo()
		servo.openWaitForAttachment(5000)

		servo.setTargetPosition(self.pos_dict['close'])
		servo.setVelocityLimit(6000)
		servo.setAcceleration(30000)
		servo.setDataRate(30)
		servo.setSpeedRampingState(True)
		servo.setEngaged(True)
		return servo

	@_is_open.default
	def _get_shuter_state(self) -> bool:
		pos = self._servo.getPosition()
		if abs(pos - self.pos_dict['open']) <= 1:
			return True
		elif abs(pos - self.pos_dict['close']) <= 1:
			return False
		else:
			self._servo.setTargetPosition(self.pos_dict['open'])
			return True

	def is_open(self) -> bool:
		return self._is_open
	
	def toggle(self):
		if self._is_open:
			self._servo.setTargetPosition(self.pos_dict['close'])
			while self._servo.getIsMoving():
				time.sleep(0.01)
				print('jo')
				print(self._servo.getPosition())
			self._is_open = False
		else:
			self._servo.setTargetPosition(self.pos_dict['open'])
			while self._servo.getIsMoving():
				time.sleep(0.01)
				print('jo')
				print(self._servo.getPosition())

			self._is_open = True

		print('final:', self._servo.getPosition(), self._servo.getIsMoving())

if __name__ == "__main__":
	sh = PhidgetShutter()
	print(sh._servo.getPosition())
	print(sh.is_open())
	for i in range(20):
		sh.toggle()
		time.sleep(1)
		sh.toggle()
		time.sleep(1)

	print(sh._servo.getPosition())