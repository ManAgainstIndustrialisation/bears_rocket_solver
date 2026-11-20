"""
Supersonic Mach number from the area ratio A / A*

A / A* has a subsonic and a supersonic solution. A nozzle exit is supersonic,
so only that branch is solved

Reference: NASA Glenn Research Center, Beginner's Guide to Aeronautics,
"Isentropic Flow Equations"
https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/isentrop/
"""

#region Imports
import numpy as np

from scipy.optimize import brentq

from .relations import stagnation_factor, area_ratio
#endregion

_M_MAX = 1e8  # Upper limit of the bracket search

def _d_area_ratio(mach, gamma):
	"""d(A/A*)/dM = A/A* * (M^2 - 1) / (M * (1 + (gamma - 1) / 2 * M^2))"""
	return area_ratio(mach, gamma) * (mach**2 - 1.0) / (mach * stagnation_factor(mach, gamma))

def supersonic_mach_from_area_ratio(eps, gamma):
	"""
	M >= 1 with A / A* = eps

	The real problem is solved with Brent's method. If eps or gamma is complex
	(complex step), one Newton step from the real root carries the derivative
	into the imaginary part exactly
	"""
	if not np.all(np.real(eps) >= 1.0):
		raise ValueError(f"Area ratio A/A* must be >= 1 (got {eps})")

	def solve_real(eps_r, gamma_r):
		residual = lambda m: area_ratio(m, gamma_r) - eps_r
		if residual(1.0) == 0.0: return 1.0

		# Double the upper bracket until it holds the root
		m_hi = 2.0
		while residual(m_hi) < 0.0:
			m_hi *= 2.0
			if m_hi > _M_MAX: raise ValueError(f"No Mach number found for A/A* = {eps_r}")

		return brentq(residual, 1.0, m_hi, xtol=1e-15, rtol=1e-15)

	mach = np.vectorize(solve_real, otypes=[float])(np.real(eps), np.real(gamma))

	if np.iscomplexobj(eps) or np.iscomplexobj(gamma):
		slope = _d_area_ratio(mach, np.real(gamma))
		mach  = mach - (area_ratio(mach, gamma) - eps) / slope

	return mach[()]
