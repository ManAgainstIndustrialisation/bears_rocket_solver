#region Imports
from openmdao.api import ExplicitComponent

from ..BEARS_Chem import BEARS_Chem
#endregion

class ChemComponent(ExplicitComponent):
	"""Equilibrium chamber state and specific impulse from the chemistry backend"""

	def initialize(self):
		self.options.declare("chem", types=BEARS_Chem)

	def setup(self):
		self.add_input("chamber_pressure", val=35e5, units="Pa")
		self.add_input("mixture_ratio",    val=6.0)
		self.add_input("expansion_ratio",  val=5.0) # Expansion area ratio
		self.add_input("eta_cstar",        val=1.0)

		self.add_output("isp",        val=120.0,  units="s")
		self.add_output("t_chamber",  val=3000.0, units="K")
		self.add_output("gamma",      val=1.2)                   # Chamber cp / cv
		self.add_output("molar_mass", val=25.0,   units="kg/kmol")

	def setup_partials(self):
		self.declare_partials(
			["isp", "t_chamber", "gamma", "molar_mass"],
			["chamber_pressure", "mixture_ratio"],
			method="fd",
			step=1e-4,
		)

		# Only the Isp depends on the expansion ratio, the chamber state does not
		self.declare_partials("isp", "expansion_ratio", method="fd", step=1e-4)

	def compute(self, inputs, outputs):
		chamber_pressure = inputs["chamber_pressure"][0]
		mixture_ratio    = inputs["mixture_ratio"][0]
		expansion_ratio  = inputs["expansion_ratio"][0]
		eta_cstar        = inputs["eta_cstar"][0]

		chem = self.options["chem"]

		isp = chem.get_isp(chamber_pressure, mixture_ratio, expansion_ratio)
		mw, gamma = chem.get_chamber_gas(chamber_pressure, mixture_ratio)

		outputs["isp"]        = eta_cstar * isp
		outputs["t_chamber"]  = chem.get_tcomb(chamber_pressure, mixture_ratio)
		outputs["gamma"]      = gamma
		outputs["molar_mass"] = mw
