#region Imports
from .comp_tank import TankComponent

from ..Config       import Gas
from ..BEARS_Thermo import PressurantThermoModel
#endregion

class PressurantTankComponent(TankComponent):
	"""Pressurant bottle, sized to push the oxidizer out of its tank"""

	def initialize(self):
		super().initialize()
		self.options.declare("gas",          types=Gas)                    # Pressurant gas
		self.options.declare("thermo_model", types=PressurantThermoModel)  # Blowdown model

	def setup(self):
		super().setup()

		self.add_input("v_ox_displace",  val=0.01,   units="m**3")  # Oxidizer volume the gas replaces
		self.add_input("p_ox",           val=70e5,   units="Pa")    # Regulated oxidizer tank pressure
		self.add_input("p_reg_margin",   val=20e5,   units="Pa")    # Bottle pressure left over p_ox at burnout
		self.add_input("ox_ullage_frac", val=0.10)                  # Oxidizer tank ullage fraction at loading [-]
		self.add_input("p_sat",          val=60e5,   units="Pa")    # Oxidizer vapor pressure, for the pad gas (Dalton's law)
		self.add_input("t_ambient",      val=303.15, units="K")     # Bottle temperature at fill

		self.add_output("m_press",     val=1.2,   units="kg")       # Pressurant mass to load, margin included
		self.add_output("rho_press",   val=344.0, units="kg/m**3")  # Pressurant density in the full bottle
		self.add_output("m_pad",       val=0.01,  units="kg")       # Gas that tops the ullage up above the vapor pressure
		self.add_output("m_burn",      val=0.30,  units="kg")       # Gas that replaces the drained oxidizer
		self.add_output("f_delivered", val=0.43)                    # Share of the bottle mass that leaves it before burnout [-]

	def setup_partials(self):
		method = "cs" if self.options["thermo_model"].supports_complex_step else "fd"
		self.declare_partials("*", "*", method=method)

	def compute(self, inputs, outputs):
		res = self.options["thermo_model"].compute(
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
