#region Imports
from .comp_tank import TankComponent

from ..BEARS_Materials import Gas
from ..BEARS_Thermo    import create_pressurant_thermo
#endregion

class PressurantTankComponent(TankComponent):

	def initialize(self):
		super().initialize()
		self.options.declare("gas",          types=Gas)
		self.options.declare("thermo_model", default=None, allow_none=True)

	def setup_fluid_inputs(self):
		self.add_input("v_ox_displace",  val=0.01,   units="m**3")
		self.add_input("p_ox",           val=70e5,   units="Pa")

		# Regulator pressure margin
		self.add_input("p_reg_margin",   val=20e5,   units="Pa")
		self.add_input("ox_ullage_frac", val=0.10)

		# Saturation (vapor) pressure of the liquid oxidizer
		# Used for pad gas sizing (Dalton's law)
		self.add_input("p_sat",          val=60e5,   units="Pa")

		# Initial bottle (ambient) temperature
		self.add_input("t_ambient",      val=303.15, units="K")

	def setup(self):
		super().setup()

		# Thermodynamic outputs
		self.add_output("m_press",     val=1.2,   units="kg")
		self.add_output("rho_press",   val=344.0, units="kg/m**3")
		self.add_output("m_pad",       val=0.01,  units="kg")
		self.add_output("m_burn",      val=0.30,  units="kg")
		self.add_output("f_delivered", val=0.43)

	def _get_thermo(self):
		return self.options["thermo_model"] or create_pressurant_thermo("auto")

	def setup_partials(self):
		method = "cs" if self._get_thermo().supports_complex_step else "fd"
		self.declare_partials("*", "*", method=method)

	def compute(self, inputs, outputs):
		res = self._get_thermo().compute(
			gas      = self.options["gas"],
			p_bottle = inputs["p_tank_max"][0],
			p_ox     = inputs["p_ox"][0],
			p_margin = inputs["p_reg_margin"][0],
			p_sat    = inputs["p_sat"][0],
			t0       = inputs["t_ambient"][0],
			v_ox     = inputs["v_ox_displace"][0],
			u_frac   = inputs["ox_ullage_frac"][0],
		)

		outputs["m_press"]     = res.m_press
		outputs["rho_press"]   = res.rho_press
		outputs["m_pad"]       = res.m_pad
		outputs["m_burn"]      = res.m_burn
		outputs["f_delivered"] = res.f_delivered

		# The pressurant fills the whole bottle, so there is no ullage
		self.size_tank(inputs, outputs, res.m_press, res.rho_press, 0.0)
