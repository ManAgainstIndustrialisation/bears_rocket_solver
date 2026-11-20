#region Imports
import numpy as np

from math         import pi
from openmdao.api import ExplicitComponent

from ..BEARS_Isentropic import (
	mass_flow_parameter,
	pressure_ratio,
	temperature_ratio,
	mach_from_area_ratio,
)
from ..Config import CONSTANTS
#endregion

g = CONSTANTS.universal.standard_gravity # Standard gravity [m/s^2]

# The nozzle is choked, so the flow at the throat is exactly sonic
MACH_THROAT = 1.0

class NozzleGeometryComponent(ExplicitComponent):
	"""
	Converging-diverging nozzle geometry

	The exit diameter is fixed and the throat area is free, so the expansion
	ratio follows from the two, eps = A_e / A_t

	The divergent section is a cone of half angle theta, whose radius grows
	linearly from r_t to r_e, so its length is L = (r_e - r_t) / tan(theta)
	"""

	def setup(self):
		self.add_input("d_exit",           val=0.065,  units="m")
		self.add_input("a_throat",         val=7.0e-4, units="m**2")
		self.add_input("half_angle",       val=0.26,   units="rad") # Conical divergent half angle

		self.add_output("a_exit",          val=3.3e-3, units="m**2")
		self.add_output("expansion_ratio", val=4.7)
		self.add_output("length",          val=0.05,   units="m")   # Divergent section, throat to exit

	def setup_partials(self):
		self.declare_partials("*", "*", method="cs")

	def compute(self, inputs, outputs):
		d_e   = inputs["d_exit"]
		a_t   = inputs["a_throat"]
		theta = inputs["half_angle"]

		a_e = 0.25 * pi * d_e**2
		r_e = 0.5 * d_e
		r_t = np.sqrt(a_t / pi)

		outputs["a_exit"]          = a_e
		outputs["expansion_ratio"] = a_e / a_t

		# Conical divergent section: tan(theta) = (r_e - r_t) / L
		outputs["length"]          = (r_e - r_t) / np.tan(theta)

class NozzleComponent(ExplicitComponent):
	"""
	Choked converging-diverging nozzle flow

	The throat is sonic (M = 1), so the isentropic choked-flow relation fixes
	the chamber pressure for a given mass flow through the throat area:

	  mdot = A_t * p_c / sqrt(R * T_c) * MFP(M = 1, gamma)

	which defines the characteristic velocity c* = sqrt(R * T_c) / MFP(1, gamma)
	"""

	def initialize(self):
		self.options.declare(
			"contour_type",
			default="conical",
			values=["ideal", "conical", "rao", "custom"],
		)

	def setup(self):
		# Propellant flow
		self.add_input("mdot_ox",          val=1.0,    units="kg/s")
		self.add_input("mixture_ratio",    val=6.0)

		# Chamber gas, from the chemistry
		self.add_input("t_chamber",        val=3000.0, units="K")
		self.add_input("gamma",            val=1.2)
		self.add_input("molar_mass",       val=25.0,   units="kg/kmol")
		self.add_input("isp",              val=300.0,  units="s")
		self.add_input("eta_cstar",        val=1.0)

		# Geometry, from the nozzle geometry component
		self.add_input("a_throat",         val=7.0e-4, units="m**2")
		self.add_input("expansion_ratio",  val=4.7)
		self.add_input("half_angle",       val=0.26,   units="rad") # Conical divergent half angle

		# Viscous friction efficiency
		self.add_input("eta_friction",     val=0.95)

		self.add_output("mach_throat",     val=1.0)
		self.add_output("mach_exit",       val=3.0)
		self.add_output("cstar",           val=1500.0, units="m/s")
		self.add_output("p_chamber",       val=30e5,   units="Pa")
		self.add_output("p_throat",        val=17e5,   units="Pa")
		self.add_output("t_throat",        val=2700.0, units="K")
		self.add_output("p_exit",          val=1e5,    units="Pa")
		self.add_output("mdot_prop",       val=1.5,    units="kg/s")
		self.add_output("thrust",          val=3000.0, units="N")
		self.add_output("isp_delivered",   val=200.0,  units="s")
		self.add_output("eta_nozzle",      val=0.96)
		self.add_output("exit_half_angle", val=15.0,   units="deg")

	def setup_partials(self):
		self.declare_partials("*", "*", method="cs")

	def compute(self, inputs, outputs):
		mdot_ox = inputs["mdot_ox"]
		mr      = inputs["mixture_ratio"]
		t_c     = inputs["t_chamber"]
		gamma   = inputs["gamma"]
		mw      = inputs["molar_mass"]
		isp     = inputs["isp"]
		eta_cs  = inputs["eta_cstar"]
		a_t     = inputs["a_throat"]
		eps     = inputs["expansion_ratio"]
		theta   = inputs["half_angle"]
		eta_fr  = inputs["eta_friction"]

		contour = self.options["contour_type"]

		RAD2DEG = 180.0 / pi

		# Divergence factor
		match contour:
			case "ideal":
				lam, theta_e = 1.0, 0.0
			case "conical":
				lam, theta_e = self._compute_conical(theta)
			case "rao":
				lam, theta_e = self._compute_rao(theta)
			case "custom":
				lam, theta_e = self._compute_custom(theta)

		eta_nozzle    = lam * eta_fr
		isp_delivered = isp * eta_nozzle

		# Choked flow through the sonic throat sets the chamber pressure
		# Molar mass [kg/kmol] -> [kg/mol] for the specific gas constant
		r_gas     = CONSTANTS.universal.molar_gas_constant / (mw * 1e-3)
		cstar     = eta_cs * np.sqrt(r_gas * t_c) / mass_flow_parameter(MACH_THROAT, gamma)
		mdot_prop = mdot_ox * (mr + 1.0) / mr
		p_c       = mdot_prop * cstar / a_t

		# Isentropic expansion to the supersonic exit, A_e / A_t = eps
		mach_e = mach_from_area_ratio(eps, gamma, supersonic=True)

		# Isp = v_e / g = F / (mdot * g)  =>  F = mdot * Isp * g
		# Modulate with nozzle efficiency
		thrust = mdot_prop * isp_delivered * g

		outputs["mach_throat"]     = MACH_THROAT
		outputs["mach_exit"]       = mach_e
		outputs["cstar"]           = cstar
		outputs["p_chamber"]       = p_c
		outputs["p_throat"]        = p_c * pressure_ratio(MACH_THROAT, gamma)
		outputs["t_throat"]        = t_c * temperature_ratio(MACH_THROAT, gamma)
		outputs["p_exit"]          = p_c * pressure_ratio(mach_e, gamma)
		outputs["mdot_prop"]       = mdot_prop
		outputs["thrust"]          = thrust
		outputs["isp_delivered"]   = isp_delivered
		outputs["eta_nozzle"]      = eta_nozzle
		outputs["exit_half_angle"] = theta_e * RAD2DEG

	#region Contour handlers
	def _compute_conical(self, theta):
		# Straight cone: the exit flow leaves at the cone half angle
		lam = 0.5 * (1.0 + np.cos(theta))
		return lam, theta

	def _compute_rao(self, theta):
		theta_e = 0.4 * theta
		lam     = 0.5 * (1.0 + np.cos(theta_e))
		return lam, theta_e

	def _compute_custom(self, theta):
		# TODO: Custom nozzle shapes, discrete radius arrays r(z)
		return self._compute_conical(theta)
	#endregion
