"""
Isentropic flow calculator

Mirrors the NASA BGA isentropic flow calculator: given the ratio of specific
heats and any one flow quantity, it solves the Mach number and every other
isentropic ratio. With known total conditions it also gives the dimensional
static state of the flow

Reference: NASA Glenn Research Center, Beginner's Guide to Aeronautics,
"Isentropic Flow Equations"
https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/isentrop/
"""

#region Imports
import math

from dataclasses import dataclass

from . import relations as rel
from . import inverse   as inv
#endregion

#region Data structures
@dataclass(frozen=True)
class FlowConditions:
	"""Dimensional static flow state at one station, in SI units"""
	pressure_pa         : float
	temperature_k       : float
	density_kgm3        : float
	speed_of_sound_ms   : float
	velocity_ms         : float
	dynamic_pressure_pa : float
	mass_flux_kgm2s     : float

@dataclass(frozen=True)
class IsentropicState:
	"""
	Every isentropic quantity at one Mach number. Ratios are static over total
	conditions, angles are in radians. The Mach and Prandtl-Meyer angles are
	NaN for subsonic flow, where they are undefined
	"""
	mach                   : float
	gamma                  : float
	temperature_ratio      : float  # T / T_t
	pressure_ratio         : float  # p / p_t
	density_ratio          : float  # rho / rho_t
	area_ratio             : float  # A / A*
	dynamic_pressure_ratio : float  # q / p
	mass_flow_parameter    : float  # mdot * sqrt(R * T_t) / (A * p_t)
	mach_angle             : float  # mu [rad]
	prandtl_meyer_angle    : float  # nu [rad]

	#region Constructors
	@classmethod
	def from_mach(cls, mach: float, gamma: float = rel.GAMMA_AIR) -> "IsentropicState":
		if not gamma > 1.0:
			raise ValueError(f"gamma must be > 1, got {gamma}")
		if not mach > 0.0:
			raise ValueError(f"Mach number must be > 0, got {mach}")

		mach       = float(mach)
		supersonic = mach >= 1.0

		return cls(
			mach                   = mach,
			gamma                  = gamma,
			temperature_ratio      = float(rel.temperature_ratio(mach, gamma)),
			pressure_ratio         = float(rel.pressure_ratio(mach, gamma)),
			density_ratio          = float(rel.density_ratio(mach, gamma)),
			area_ratio             = float(rel.area_ratio(mach, gamma)),
			dynamic_pressure_ratio = float(rel.dynamic_pressure_ratio(mach, gamma)),
			mass_flow_parameter    = float(rel.mass_flow_parameter(mach, gamma)),
			mach_angle             = (
				float(rel.mach_angle(mach)) if supersonic else math.nan
			),
			prandtl_meyer_angle    = (
				float(rel.prandtl_meyer_angle(mach, gamma)) if supersonic else math.nan
			),
		)

	@classmethod
	def from_quantity(
		cls,
		quantity   : str,
		value      : float,
		gamma      : float = rel.GAMMA_AIR,
		supersonic : bool | None = None,
	) -> "IsentropicState":
		"""
		Solve the state from any one quantity, named as the matching field of
		this class (e.g. "pressure_ratio", "area_ratio", "prandtl_meyer_angle").
		"area_ratio" and "mass_flow_parameter" need the `supersonic` branch
		"""
		if not gamma > 1.0:
			raise ValueError(f"gamma must be > 1, got {gamma}")

		match quantity:
			case "mach":
				mach = value
			case "temperature_ratio":
				mach = inv.mach_from_temperature_ratio(value, gamma)
			case "pressure_ratio":
				mach = inv.mach_from_pressure_ratio(value, gamma)
			case "density_ratio":
				mach = inv.mach_from_density_ratio(value, gamma)
			case "dynamic_pressure_ratio":
				mach = inv.mach_from_dynamic_pressure_ratio(value, gamma)
			case "mach_angle":
				mach = inv.mach_from_mach_angle(value)
			case "prandtl_meyer_angle":
				mach = inv.mach_from_prandtl_meyer_angle(value, gamma)
			case "area_ratio" | "mass_flow_parameter":
				if supersonic is None:
					raise ValueError(
						f"'{quantity}' has a subsonic and a supersonic "
						"solution, pass supersonic=True or False"
					)
				solve = (
					inv.mach_from_area_ratio if quantity == "area_ratio"
					else inv.mach_from_mass_flow_parameter
				)
				mach = solve(value, gamma, supersonic=supersonic)
			case _:
				raise ValueError(f"Unknown isentropic quantity: '{quantity}'")

		return cls.from_mach(float(mach), gamma)
	#endregion

	#region Dimensional state
	def static_conditions(
		self,
		p_total_pa : float,
		t_total_k  : float,
		r_specific : float = rel.R_AIR,
	) -> FlowConditions:
		"""Static flow state from total pressure and temperature"""
		p   = p_total_pa * self.pressure_ratio
		t   = t_total_k  * self.temperature_ratio
		rho = p / (r_specific * t)
		a   = float(rel.speed_of_sound(t, self.gamma, r_specific))
		v   = self.mach * a

		return FlowConditions(
			pressure_pa         = p,
			temperature_k       = t,
			density_kgm3        = rho,
			speed_of_sound_ms   = a,
			velocity_ms         = v,
			dynamic_pressure_pa = 0.5 * rho * v**2,
			mass_flux_kgm2s     = rho * v,
		)
	#endregion

	#region Output
	def __str__(self) -> str:
		rows = [
			("Mach number",            "M",            self.mach),
			("Ratio of specific heats","gamma",        self.gamma),
			("Temperature ratio",      "T/Tt",         self.temperature_ratio),
			("Pressure ratio",         "p/pt",         self.pressure_ratio),
			("Density ratio",          "rho/rhot",     self.density_ratio),
			("Area ratio",             "A/A*",         self.area_ratio),
			("Dynamic pressure ratio", "q/p",          self.dynamic_pressure_ratio),
			("Mass flow parameter",    "mdot*sqrt(RTt)/(A*pt)", self.mass_flow_parameter),
			("Mach angle",             "mu [deg]",     math.degrees(self.mach_angle)),
			("Prandtl-Meyer angle",    "nu [deg]",     math.degrees(self.prandtl_meyer_angle)),
		]
		return "\n".join(
			f"{name:<24}{symbol:<23}{value:12.5f}" for name, symbol, value in rows
		)
	#endregion
#endregion
