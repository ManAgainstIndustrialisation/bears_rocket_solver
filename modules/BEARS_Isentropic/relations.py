"""
Isentropic flow relations of a calorically perfect ideal gas

Every ratio is a static quantity over its total (stagnation) value, written as
a function of the Mach number M and the ratio of specific heats gamma. All
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
#endregion

#region Helpers
def stagnation_factor(mach, gamma):
	"""T_t / T = 1 + (gamma - 1) / 2 * M^2"""
	return 1.0 + 0.5 * (gamma - 1.0) * mach**2

def _area_exponent(gamma):
	"""(gamma + 1) / (2 * (gamma - 1)), shared by A/A* and the mass flow"""
	return (gamma + 1.0) / (2.0 * (gamma - 1.0))
#endregion

#region Static-to-total ratios
def temperature_ratio(mach, gamma):
	"""T / T_t = (1 + (gamma - 1) / 2 * M^2)^-1"""
	return 1.0 / stagnation_factor(mach, gamma)

def pressure_ratio(mach, gamma):
	"""p / p_t = (T / T_t)^(gamma / (gamma - 1))"""
	return temperature_ratio(mach, gamma) ** (gamma / (gamma - 1.0))
#endregion

#region Area and mass flow
def area_ratio(mach, gamma):
	"""
	A / A* = 1 / M * [2 / (gamma + 1) * (1 + (gamma - 1) / 2 * M^2)]
	         ^ ((gamma + 1) / (2 * (gamma - 1)))

	A* is the sonic (choked) throat area where M = 1. Every A / A* > 1 maps to
	one subsonic and one supersonic Mach number
	"""
	base = 2.0 / (gamma + 1.0) * stagnation_factor(mach, gamma)
	return base ** _area_exponent(gamma) / mach

def mass_flow_parameter(mach, gamma):
	"""
	Dimensionless mass flow per unit area,

	  mdot * sqrt(R * T_t) / (A * p_t)
	    = sqrt(gamma) * M * (1 + (gamma - 1) / 2 * M^2)
	      ^ -((gamma + 1) / (2 * (gamma - 1)))

	It peaks at M = 1, i.e. choked flow
	"""
	return (
		np.sqrt(gamma) * mach
		* stagnation_factor(mach, gamma) ** -_area_exponent(gamma)
	)
#endregion
