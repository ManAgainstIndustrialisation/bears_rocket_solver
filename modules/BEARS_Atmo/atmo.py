#region Imports
from importlib.util import find_spec

import numpy as np

from ..Config import CONSTANTS, Air
#endregion

class BEARS_Atm:
	"""
	Static atmosphere against altitude. Calling it with an altitude [m] gives
	(temperature [K], pressure [Pa], density [kg/m^3], speed of sound [m/s])
	"""

	def __init__(self, model: str, air: Air):
		"""`model` is the [models] atmosphere choice: auto, isacalc or standalone"""
		if model == "auto":
			model = "isacalc" if find_spec("isacalc") else "standalone"

		self.air = air  # Air properties for the standalone model

		match model:
			case "isacalc":
				# isacalc carries its own ISA constants
				import isacalc
				self._isa  = isacalc.Atmosphere()
				self._call = self._isacalc
			case "standalone":
				self._call = self._standalone

	def __call__(self, altitude):
		return self._call(altitude)

	def _isacalc(self, h):
		val = self._isa.calculate(h)
		return val[1], val[2], val[3], val[4]

	def _standalone(self, h):
		"""
		ISA troposphere

		TODO: AI-generated placeholder, only valid up to the tropopause (11 km):
		above it the temperature is held but the pressure still follows the
		troposphere law
		"""
		isa = CONSTANTS.atmosphere
		g0  = CONSTANTS.universal.standard_gravity
		R   = CONSTANTS.universal.molar_gas_constant
		air = self.air

		T0, L = isa.sea_level_temperature, isa.lapse_rate

		T   = np.maximum(T0 - L * h, isa.tropopause_temperature)
		P   = isa.sea_level_pressure * (T / T0)**(g0 * air.molar_mass / (R * L))
		rho = P / (air.r_specific * T)
		a   = np.sqrt(air.gamma * air.r_specific * T)

		return T, P, rho, a
