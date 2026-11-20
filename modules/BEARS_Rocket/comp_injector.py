#region Imports
import numpy as np

from openmdao.api import ExplicitComponent
#endregion

class InjectorComponent(ExplicitComponent):
	"""
	Oxidizer mass flow through the injector orifices, from incompressible
	orifice flow: mdot = cd * A * sqrt(2 * rho * dp), see
	https://en.wikipedia.org/wiki/Orifice_plate
	"""

	def initialize(self):
		self.options.declare("rho_ox", types=float)  # Liquid oxidizer density [kg/m^3]

	def setup(self):
		self.add_input("p_tank",    val=30e5,   units="Pa")    # Oxidizer tank pressure, upstream
		self.add_input("p_chamber", val=20e5,   units="Pa")    # Chamber pressure, downstream
		self.add_input("a_inj",     val=4.5e-5, units="m**2")  # Total orifice area
		self.add_input("cd",        val=0.7)                   # Discharge coefficient [-]

		self.add_output("mdot_ox", val=1.0,  units="kg/s")     # Oxidizer mass flow
		self.add_output("delta_p", val=10e5, units="Pa")       # Pressure drop across the injector

	def setup_partials(self):
		self.declare_partials("mdot_ox", "*", method="cs")

		self.declare_partials("delta_p", "p_tank",    val=1.0)
		self.declare_partials("delta_p", "p_chamber", val=-1.0)

	def compute(self, inputs, outputs):
		rho     = self.options["rho_ox"]
		delta_p = inputs["p_tank"] - inputs["p_chamber"]

		# Newton iterations can reverse the pressure drop, which reverses the
		# flow. The sign is taken from the real part only, so complex step
		# still carries the derivative through sqrt(sign * dp)
		sign = np.sign(np.real(delta_p))

		outputs["mdot_ox"] = sign * inputs["cd"] * inputs["a_inj"] * np.sqrt(2.0 * rho * sign * delta_p)
		outputs["delta_p"] = delta_p
