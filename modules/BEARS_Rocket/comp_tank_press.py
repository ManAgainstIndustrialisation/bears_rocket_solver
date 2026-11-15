# region Imports
import numpy as np

from math       import pi
from .comp_tank import TankComponent

from ..BEARS_Materials import Gas, NITROGEN
from ..BEARS_Thermo    import create_pressurant_thermo
# endregion

class PressurantTankComponent(TankComponent):

	def initialize(self):
		super().initialize()
		self.options.declare("gas",          default=NITROGEN, types=Gas)

		# Alternative options for passing gas parameters
		self.options.declare("r_gas",        default=296.8,    types=float)
		self.options.declare("gamma_gas",    default=1.40,     types=float)
		self.options.declare("t_ambient_k",  default=303.15,   types=float)

		# * Compressibility factor
		self.options.declare("z_factor",     default=1.15,     types=float)

		# * Saturation (vapor) pressure of the liquid oxidizer
		# Used for pad gas sizing (Dalton's law)
		self.options.declare("p_sat",        default=63.08e5,  types=float)
		self.options.declare("thermo_model", default=None,     allow_none=True)

	def setup_fluid_inputs(self):
		self.add_input("v_ox_displace",  val=0.01, units="m**3")
		self.add_input("p_ox",           val=70e5, units="Pa")

		# Regulator pressure margin
		self.add_input("p_reg_margin",   val=20e5, units="Pa")
		self.add_input("ox_ullage_frac", val=0.10)

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

	def compute_thermo(self, inputs):
		gas = self.options["gas"] or Gas(
			name       = "Custom",
			molar_mass = 28.0134, # TODO
			r_specific = self.options["r_gas"],
			gamma      = self.options["gamma_gas"],
			z_factor   = self.options["z_factor"],
		)

		res = self._get_thermo().compute(
			gas = gas,
			p_bottle = inputs["p_tank_max"][0],
			p_ox     = inputs["p_ox"][0],
			p_margin = inputs["p_reg_margin"][0],
			p_sat    = self.options["p_sat"],
			t0       = self.options["t_ambient_k"],
			v_ox     = inputs["v_ox_displace"][0],
			u_frac   = inputs["ox_ullage_frac"][0],
		)

		return (
			res.m_press,
			res.rho_press,
			res.m_pad,
			res.m_burn,
			res.f_delivered,
		)

	def get_fluid_density(self, inputs):
		_, rho_press, _, _, _ = self.compute_thermo(inputs)
		return rho_press

	def get_fluid_mass(self, inputs):
		m_press, _, _, _, _ = self.compute_thermo(inputs)
		return m_press

	def get_ullage_frac(self, inputs):
		return 0.0

	def compute(self, inputs, outputs):
		m_pr, rho_pr, m_pad, m_burn, f_del = self.compute_thermo(inputs)

		outputs["m_press"]     = m_pr
		outputs["rho_press"]   = rho_pr
		outputs["m_pad"]       = m_pad
		outputs["m_burn"]      = m_burn
		outputs["f_delivered"] = f_del

		super().compute(inputs, outputs)

