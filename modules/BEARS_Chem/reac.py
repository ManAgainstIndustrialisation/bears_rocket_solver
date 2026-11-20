#region Imports
from typing         import Optional
from ..Config       import SpeciesConfig, CONSTANTS
#endregion

class Reactant:
	reactype       : str
	name           : str
	mass_fraction  : float
	formula_parts  : tuple[dict[str, float], ...]
	formula        : dict[str, float]
	temperature    : Optional[float]
	enthalpy       : Optional[float]
	enthalpy_units : Optional[str]
	density        : Optional[float]
	density_units  : Optional[str]
	vapor_pressure : Optional[float]

	def __init__(self, reacdict: dict):
		"""Construct a Reactant object from a dictionary"""

		# Required reactant parameters
		self.reactype      = reacdict["reactype"]
		self.name          = reacdict["name"]
		self.formula_parts = tuple(reacdict.get("formula_parts", ()))

		# Optional
		self.mass_fraction  = reacdict.get("mass_fraction",  100.0)
		self.temperature    = reacdict.get("temperature",    CONSTANTS.reference.temperature)
		self.enthalpy       = reacdict.get("enthalpy")
		self.enthalpy_units = reacdict.get("enthalpy_units", "cal/mol")
		self.density        = reacdict.get("density")
		self.density_units  = reacdict.get("density_units")
		self.vapor_pressure = reacdict.get("vapor_pressure_bar")

		self.compile_formula()

	@classmethod
	def from_config(cls, cfg: SpeciesConfig) -> "Reactant":
		return cls({
			"name"               : cfg.name,
			"reactype"           : cfg.role or "fuel",
			"formula_parts"      : cfg.formula_parts,
			"mass_fraction"      : cfg.mass_fraction,
			"temperature"        : cfg.temperature_k,
			"enthalpy"           : cfg.enthalpy,
			"enthalpy_units"     : cfg.enthalpy_units,
			"density"            : cfg.density,
			"density_units"      : cfg.density_units,
			"vapor_pressure_bar" : cfg.vapor_pressure_bar,
		})

	def compile_formula(self):
		"""
		Compile the formula components as specified in the JSON input into a
		complete formula
		"""
		self.formula: dict[str, float] = {}
		for part in self.formula_parts:
			for k, v in part.items():
				self.formula[k] = self.formula.get(k, 0) + v

	def get_density_si(self) -> float:
		"""Return density in kg/m^3"""
		if self.density is None:
			raise ValueError(f"Reactant '{self.name}' has no density")
		if self.density_units in ["g/cm^3", "g/cc", "g/cm3"]:
			return self.density * 1000.0
		return self.density
