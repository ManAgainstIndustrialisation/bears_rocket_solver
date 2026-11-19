#region Imports
from .comp_tank import TankComponent
#endregion

class OxidizerTankComponent(TankComponent):

	def initialize(self):
		super().initialize()
		self.options.declare("rho_ox", types=float)

	def setup_fluid_inputs(self):
		self.add_input("m_oxy",       val=10.0, units="kg")
		self.add_input("ullage_frac", val=0.01)

	def fluid_state(self, inputs):
		return inputs["m_oxy"], self.options["rho_ox"], inputs["ullage_frac"]
