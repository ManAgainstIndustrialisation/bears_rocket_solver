#region Imports
import os

from pathlib import Path

from ..Config import BipropellantConfig, CONSTANTS

from .reac         import Reactant
from .helpers      import bulk_density
from .backend_base import ThermochemistryBackend
#endregion

class BEARS_Chem:
	"""Unified thermochemistry evaluation interface for OpenMDAO"""

	def __init__(
		self,
		backend  : ThermochemistryBackend,
		rho_ox   : float,
		rho_fuel : float,
		p_vap_ox : float | None = None,
	):
		self._backend = backend
		self.rho_ox   = rho_ox
		self.rho_fuel = rho_fuel
		self.p_vap_ox = p_vap_ox # Oxidizer saturation pressure [Pa]

	@classmethod
	def set_work_dir(cls, path: str | Path):
		try:
			import rocketcea.cea_obj as cea_obj
			abs_path = os.path.abspath(path)
			os.makedirs(abs_path, exist_ok=True)
			cea_obj.ROCKETCEA_DATA_DIR = abs_path
		except ImportError:
			pass

	@classmethod
	def from_config(
		cls,
		config   : BipropellantConfig,
		backend  : str = "auto",
		work_dir : str | Path | None = None,
	) -> "BEARS_Chem":
		from importlib.util import find_spec

		if work_dir is not None:
			cls.set_work_dir(work_dir)

		ox_reactants   = tuple(Reactant.from_config(r) for r in config.oxidizers)
		fuel_reactants = tuple(Reactant.from_config(r) for r in config.fuels)

		rho_ox   = bulk_density(ox_reactants)
		rho_fuel = bulk_density(fuel_reactants)

		# Saturation pressure of a single-species oxidizer, in Pa
		p_vap_ox = None
		if len(ox_reactants) == 1 and ox_reactants[0].vapor_pressure is not None:
			p_vap_ox = ox_reactants[0].vapor_pressure * 1e5

		selected = backend.lower()
		if selected == "auto":
			selected = "cea" if find_spec("cea") else "rocketcea"

		match selected:
			case "cea":
				from .backend_cea import CEABackend
				engine = CEABackend(ox_reactants, fuel_reactants)
			case "rocketcea":
				from .backend_rocketcea import RocketCEABackend
				engine = RocketCEABackend(ox_reactants, fuel_reactants)
			case _:
				raise ValueError(f"Unknown chemistry backend: '{backend}'")

		return cls(engine, rho_ox, rho_fuel, p_vap_ox)

	def get_chamber_gas(self, pc_pa: float, mr: float) -> tuple[float, float]:
		"""Chamber gas (molar mass [kg/kmol], ratio of specific heats)"""
		return self._backend.get_chamber_gas(pc_pa, mr)

	def get_tcomb(self, pc_pa: float, mr: float) -> float:
		return self._backend.get_tcomb(pc_pa, mr)

	def get_isp(
		self,
		pc_pa    : float,
		mr       : float,
		eps      : float,
		p_amb_pa : float = CONSTANTS.atmosphere.sea_level_pressure,
	) -> float:
		return self._backend.get_isp(pc_pa, mr, eps, p_amb_pa)
