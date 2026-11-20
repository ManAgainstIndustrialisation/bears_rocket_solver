#region Imports
import os

from importlib.util import find_spec
from pathlib        import Path

from ..Config      import Propellants, Species
from .backend_base import CombustionState
#endregion

def bulk_density(blend: tuple[Species, ...]) -> float:
	"""Density of a blend mixed by mass_fraction [kg/m^3]"""
	total = sum(s.mass_fraction for s in blend)
	return 1.0 / sum((s.mass_fraction / total) / s.density for s in blend)

class BEARS_Chem:
	"""Combustion chemistry of one propellant combination"""

	def __init__(self, propellants: Propellants, backend: str):
		"""`backend` is the [models] chemistry choice: auto, cea or rocketcea"""
		self.rho_ox   = propellants.oxidizer.density         # Liquid oxidizer density [kg/m^3]
		self.rho_fuel = bulk_density(propellants.fuels)      # Fuel grain density [kg/m^3]
		self.p_vap_ox = propellants.oxidizer.vapor_pressure  # Oxidizer saturation pressure [Pa]

		if backend == "auto":
			backend = "cea" if find_spec("cea") else "rocketcea"

		match backend:
			case "cea":
				from .backend_cea import CEABackend
				self._backend = CEABackend(propellants)
			case "rocketcea":
				from .backend_rocketcea import RocketCEABackend
				self._backend = RocketCEABackend(propellants)

	@staticmethod
	def set_work_dir(path: str | Path):
		"""Keep the RocketCEA scratch files in `path`, if RocketCEA is installed"""
		if find_spec("rocketcea") is None: return

		import rocketcea.cea_obj as cea_obj
		abs_path = os.path.abspath(path)
		os.makedirs(abs_path, exist_ok=True)
		cea_obj.ROCKETCEA_DATA_DIR = abs_path

	def evaluate(self, pc_pa: float, mr: float, eps: float) -> CombustionState:
		"""Equilibrium state at chamber pressure [Pa], mixture ratio and expansion ratio"""
		return self._backend.evaluate(pc_pa, mr, eps)
