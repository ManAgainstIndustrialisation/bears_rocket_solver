"""
Isentropic flow relations of a calorically perfect ideal gas

Every ratio is a static quantity over its total (stagnation) value, written as a
function of the Mach number M and the ratio of specific heats gamma. All
functions accept scalars or NumPy arrays, real or complex, so they can be used
inside complex-step OpenMDAO components

The relations hold only for reversible, adiabatic flow, i.e. gradual changes
such as flow through a nozzle. They do not hold across shock waves

Reference: NASA Glenn Research Center, Beginner's Guide to Aeronautics,
"Isentropic Flow Equations"
https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/isentrop/
"""

#region Imports
import numpy as np

from ..Config import CONSTANTS
#endregion

# Defaults for air, from the physical constants file
GAMMA_AIR = CONSTANTS.air.gamma
R_AIR     = CONSTANTS.air.r_specific

#region Helpers
def stagnation_factor(mach, gamma=GAMMA_AIR):
	"""T_t / T = 1 + (gamma - 1) / 2 * M^2"""
	return 1.0 + 0.5 * (gamma - 1.0) * mach**2

def _area_exponent(gamma):
	"""(gamma + 1) / (2 * (gamma - 1)), shared by A/A* and the mass flow"""
	return (gamma + 1.0) / (2.0 * (gamma - 1.0))

def _require(condition, message: str):
	if not np.all(condition):
		raise ValueError(message)
#endregion

#region Gas properties
def speed_of_sound(temperature, gamma=GAMMA_AIR, r_specific=R_AIR):
	"""a = sqrt(gamma * R * T), with R the specific gas constant [J/(kg*K)]"""
	return np.sqrt(gamma * r_specific * temperature)

def mach_number(velocity, temperature, gamma=GAMMA_AIR, r_specific=R_AIR):
	"""M = v / a"""
	return velocity / speed_of_sound(temperature, gamma, r_specific)
#endregion

#region Static-to-total ratios
def temperature_ratio(mach, gamma=GAMMA_AIR):
	"""T / T_t = (1 + (gamma - 1) / 2 * M^2)^-1"""
	return 1.0 / stagnation_factor(mach, gamma)

def pressure_ratio(mach, gamma=GAMMA_AIR):
	"""p / p_t = (T / T_t)^(gamma / (gamma - 1))"""
	return temperature_ratio(mach, gamma) ** (gamma / (gamma - 1.0))

def density_ratio(mach, gamma=GAMMA_AIR):
	"""rho / rho_t = (T / T_t)^(1 / (gamma - 1))"""
	return temperature_ratio(mach, gamma) ** (1.0 / (gamma - 1.0))

def dynamic_pressure_ratio(mach, gamma=GAMMA_AIR):
	"""q / p = gamma / 2 * M^2, from q = rho * v^2 / 2 = gamma * p * M^2 / 2"""
	return 0.5 * gamma * mach**2
#endregion

#region Area and mass flow
def area_ratio(mach, gamma=GAMMA_AIR):
	"""
	A / A* = 1 / M * [2 / (gamma + 1) * (1 + (gamma - 1) / 2 * M^2)]
	         ^ ((gamma + 1) / (2 * (gamma - 1)))

	A* is the sonic (choked) throat area where M = 1. Every A / A* > 1 maps to
	one subsonic and one supersonic Mach number
	"""
	_require(np.real(mach) > 0.0, "Area ratio requires M > 0")

	base = 2.0 / (gamma + 1.0) * stagnation_factor(mach, gamma)
	return base ** _area_exponent(gamma) / mach

def mass_flow_parameter(mach, gamma=GAMMA_AIR):
	"""
	Dimensionless mass flow per unit area,

	  mdot * sqrt(R * T_t) / (A * p_t)
	    = sqrt(gamma) * M * (1 + (gamma - 1) / 2 * M^2)
	      ^ -((gamma + 1) / (2 * (gamma - 1)))

	It peaks at M = 1, i.e. choked flow. The BGA calculator's corrected airflow
	Wcor/A is this parameter scaled by sea-level standard-day p_t and T_t
	"""
	return (
		np.sqrt(gamma) * mach
		* stagnation_factor(mach, gamma) ** -_area_exponent(gamma)
	)

def mass_flux(mach, p_total, t_total, gamma=GAMMA_AIR, r_specific=R_AIR):
	"""mdot / A = p_t / sqrt(R * T_t) * mass_flow_parameter(M) [kg/(m^2*s)]"""
	return (
		p_total / np.sqrt(r_specific * t_total)
		* mass_flow_parameter(mach, gamma)
	)

def choked_mass_flow(a_throat, p_total, t_total, gamma=GAMMA_AIR, r_specific=R_AIR):
	"""mdot through a sonic throat of area A* [kg/s]"""
	return a_throat * mass_flux(1.0, p_total, t_total, gamma, r_specific)
#endregion

#region Supersonic angles
def mach_angle(mach):
	"""mu = arcsin(1 / M) [rad], defined for M >= 1"""
	_require(np.real(mach) >= 1.0, "Mach angle requires M >= 1")
	return np.arcsin(1.0 / mach)

def prandtl_meyer_angle(mach, gamma=GAMMA_AIR):
	"""
	nu = sqrt((gamma + 1) / (gamma - 1))
	     * arctan(sqrt((gamma - 1) / (gamma + 1) * (M^2 - 1)))
	     - arctan(sqrt(M^2 - 1))                                    [rad]

	The angle a sonic flow must turn through to expand isentropically to M,
	defined for M >= 1
	"""
	_require(np.real(mach) >= 1.0, "Prandtl-Meyer angle requires M >= 1")

	k   = np.sqrt((gamma + 1.0) / (gamma - 1.0))
	msm = mach**2 - 1.0
	return k * np.arctan(np.sqrt(msm) / k) - np.arctan(np.sqrt(msm))

def prandtl_meyer_max(gamma=GAMMA_AIR):
	"""nu as M -> infinity: pi / 2 * (sqrt((gamma + 1) / (gamma - 1)) - 1) [rad]"""
	return 0.5 * np.pi * (np.sqrt((gamma + 1.0) / (gamma - 1.0)) - 1.0)
#endregion
