#region Imports
from openmdao.api import ExplicitComponent

from ..BEARS_Chem import BEARS_Chem
#endregion

class ChemComponent(ExplicitComponent):
	"""
	Equilibrium chamber state and specific impulse from the chemistry backend

	CEA is real-valued only, so the partials are finite differences
	"""

	def initialize(self):
		self.options.declare("chem", types=BEARS_Chem)  # Chemistry of the propellant combination

	def setup(self):
		self.add_input("chamber_pressure", val=35e5, units="Pa")  # Chamber pressure
		self.add_input("mixture_ratio",    val=6.0)               # Oxidizer over fuel mass flow [-]
		self.add_input("expansion_ratio",  val=5.0)               # Nozzle exit over throat area [-]
		self.add_input("eta_cstar",        val=1.0)               # Combustion efficiency on c* and Isp [-]

		self.add_output("isp",        val=200.0,  units="s")       # Sea-level Isp, combustion losses included
		self.add_output("t_chamber",  val=3000.0, units="K")       # Adiabatic flame temperature
		self.add_output("gamma",      val=1.2)                     # Ratio of specific heats of the chamber gas [-]
		self.add_output("molar_mass", val=0.025,  units="kg/mol")  # Molar mass of the chamber gas

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
		state = self.options["chem"].evaluate(
			inputs["chamber_pressure"][0],
			inputs["mixture_ratio"][0],
			inputs["expansion_ratio"][0],
		)

		outputs["isp"]        = inputs["eta_cstar"] * state.isp
		outputs["t_chamber"]  = state.t_chamber
		outputs["gamma"]      = state.gamma
		outputs["molar_mass"] = state.molar_mass
