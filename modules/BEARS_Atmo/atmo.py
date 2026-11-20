#region imports
import numpy   as np

try:
	import isacalc as isa
except ImportError:
	isa = None

from ..Config import CONSTANTS, AIR
#endregion

def atm_isa(h):
	std_atm = isa.Atmosphere()
	val = std_atm.calculate(h)

	# T, P, rho, a
	return val[1], val[2], val[3], val[4]

def atm_standalone(h):
	"""
	Standalone logic for ISA atmosphere

	NOTE: AI-generated placeholder
	"""

	isa = CONSTANTS.atmosphere
	air = AIR
	g0  = CONSTANTS.universal.standard_gravity

	T0 = isa.sea_level_temperature
	L  = isa.lapse_rate

	T   = np.maximum(T0 - L * h, isa.tropopause_temperature)
	R   = CONSTANTS.universal.molar_gas_constant
	P   = isa.sea_level_pressure * (T / T0)**(g0 * air.molar_mass / (R * L))
	rho = P / (air.r_specific * T)
	a   = np.sqrt(air.gamma * air.r_specific * T)

	return T, P, rho, a

model_map = {
	"isacalc": atm_isa,
	"standalone": atm_standalone
}

atmosphere_models = list(model_map.keys())

class BEARS_Atm:
	def __init__(self, model: str = "auto"):
		match model:
			case "auto":
				self.model = "isacalc" if isa is not None else "standalone"
			case "isacalc":
				if isa is None:
					raise ImportError("isacalc package is not installed")
				self.model = model
			case "standalone":
				self.model = model
			case _:
				raise ValueError(f"Unknown atmosphere model: '{model}'")

	def __call__(self, altitude: float):
		return model_map[self.model](altitude)
