"""
Mach number from any one known isentropic quantity

Fixing a single ratio fixes the Mach number, and with it every other ratio.
The temperature, pressure, density, dynamic pressure and Mach angle relations
invert in closed form. The area ratio, mass flow parameter and Prandtl-Meyer
angle are solved numerically

A / A* and the mass flow parameter are double-valued with a subsonic and a
supersonic solution, so those inversions take an explicit `supersonic` flag

Reference: NASA Glenn Research Center, Beginner's Guide to Aeronautics,
"Isentropic Flow Equations"
https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/isentrop/
"""

#region Imports
import numpy as np

from scipy.optimize import brentq

from .relations import (
	GAMMA_AIR,
	stagnation_factor,
	area_ratio,
	mass_flow_parameter,
	prandtl_meyer_angle,
	prandtl_meyer_max,
	_require,
)
#endregion

#region Root finding
_M_MIN = 1e-12  # Lower bracket for subsonic branches, where A/A* -> infinity
_M_MAX = 1e8    # Bracket growth limit for supersonic branches

def _solve_mach(func, dfunc, target, gamma, m_lo, m_hi, grow=False):
	"""
	Solve func(M, gamma) = target for M within [m_lo, m_hi], where func is
	monotonic in M on that interval

	With `grow`, m_hi is doubled until the root is bracketed. The real problem
	is solved with Brent's method. If the target or gamma is complex (complex
	step), one Newton step from the real root carries the derivative into the
	imaginary part exactly
	"""
	target = np.asarray(target)
	gamma  = np.asarray(gamma)

	def solve_one(y, gam):
		residual = lambda m: func(m, gam) - y
		tol      = 1e-13 * max(1.0, abs(y))

		lo, hi = m_lo, m_hi
		if abs(residual(lo)) <= tol: return lo
		while grow and residual(lo) * residual(hi) > 0.0:
			hi *= 2.0
			if hi > _M_MAX:
				raise ValueError(f"No Mach number found for value {y}")
		if abs(residual(hi)) <= tol: return hi

		return brentq(residual, lo, hi, xtol=1e-15, rtol=1e-15)

	mach = np.vectorize(solve_one, otypes=[float])(np.real(target), np.real(gamma))

	if np.iscomplexobj(target) or np.iscomplexobj(gamma):
		slope = dfunc(mach, np.real(gamma))
		with np.errstate(divide="ignore", invalid="ignore"):
			step = (func(mach, gamma) - target) / slope
		mach = np.where(slope != 0.0, mach - step, mach)

	return mach[()]
#endregion

#region Closed-form inversions
def mach_from_temperature_ratio(t_ratio, gamma=GAMMA_AIR):
	"""M from T / T_t, which lies in (0, 1]"""
	_require(
		(np.real(t_ratio) > 0.0) & (np.real(t_ratio) <= 1.0),
		"Temperature ratio T/T_t must be in (0, 1]",
	)
	return np.sqrt(2.0 / (gamma - 1.0) * (1.0 / t_ratio - 1.0))

def mach_from_pressure_ratio(p_ratio, gamma=GAMMA_AIR):
	"""M from p / p_t, which lies in (0, 1]"""
	_require(
		(np.real(p_ratio) > 0.0) & (np.real(p_ratio) <= 1.0),
		"Pressure ratio p/p_t must be in (0, 1]",
	)
	t_ratio = p_ratio ** ((gamma - 1.0) / gamma)
	return mach_from_temperature_ratio(t_ratio, gamma)

def mach_from_density_ratio(rho_ratio, gamma=GAMMA_AIR):
	"""M from rho / rho_t, which lies in (0, 1]"""
	_require(
		(np.real(rho_ratio) > 0.0) & (np.real(rho_ratio) <= 1.0),
		"Density ratio rho/rho_t must be in (0, 1]",
	)
	t_ratio = rho_ratio ** (gamma - 1.0)
	return mach_from_temperature_ratio(t_ratio, gamma)

def mach_from_dynamic_pressure_ratio(q_ratio, gamma=GAMMA_AIR):
	"""M from q / p = gamma / 2 * M^2"""
	_require(np.real(q_ratio) >= 0.0, "Dynamic pressure ratio q/p must be >= 0")
	return np.sqrt(2.0 * q_ratio / gamma)

def mach_from_mach_angle(mu):
	"""M from the Mach angle mu [rad], which lies in (0, pi/2]"""
	_require(
		(np.real(mu) > 0.0) & (np.real(mu) <= 0.5 * np.pi),
		"Mach angle must be in (0, pi/2] rad",
	)
	return 1.0 / np.sin(mu)
#endregion

#region Numerical inversions
def _d_area_ratio(mach, gamma):
	"""d(A/A*)/dM = A/A* * (M^2 - 1) / (M * (1 + (gamma - 1) / 2 * M^2))"""
	fac = stagnation_factor(mach, gamma)
	return area_ratio(mach, gamma) * (mach**2 - 1.0) / (mach * fac)

def _d_mass_flow_parameter(mach, gamma):
	"""d(MFP)/dM = -MFP * (M^2 - 1) / (M * (1 + (gamma - 1) / 2 * M^2))"""
	fac = stagnation_factor(mach, gamma)
	return -mass_flow_parameter(mach, gamma) * (mach**2 - 1.0) / (mach * fac)

def _d_prandtl_meyer_angle(mach, gamma):
	"""d(nu)/dM = sqrt(M^2 - 1) / (M * (1 + (gamma - 1) / 2 * M^2))"""
	fac = stagnation_factor(mach, gamma)
	return np.sqrt(mach**2 - 1.0) / (mach * fac)

def mach_from_area_ratio(area_ratio_value, gamma=GAMMA_AIR, *, supersonic: bool):
	"""M from A / A* >= 1, on the subsonic or supersonic branch"""
	_require(np.real(area_ratio_value) >= 1.0, "Area ratio A/A* must be >= 1")

	m_lo, m_hi = (1.0, 2.0) if supersonic else (_M_MIN, 1.0)
	return _solve_mach(
		area_ratio, _d_area_ratio,
		area_ratio_value, gamma, m_lo, m_hi, grow=supersonic,
	)

def mach_from_mass_flow_parameter(mfp, gamma=GAMMA_AIR, *, supersonic: bool):
	"""
	M from the mass flow parameter mdot * sqrt(R * T_t) / (A * p_t), on the
	subsonic or supersonic branch. It cannot exceed its choked value at M = 1
	"""
	mfp_choked = float(np.real(mass_flow_parameter(1.0, gamma)))
	_require(
		(np.real(mfp) > 0.0) & (np.real(mfp) <= mfp_choked * (1.0 + 1e-12)),
		f"Mass flow parameter must be in (0, {mfp_choked:.5f}] (choked flow)",
	)

	m_lo, m_hi = (1.0, 2.0) if supersonic else (_M_MIN, 1.0)
	return _solve_mach(
		mass_flow_parameter, _d_mass_flow_parameter,
		mfp, gamma, m_lo, m_hi, grow=supersonic,
	)

def mach_from_prandtl_meyer_angle(nu, gamma=GAMMA_AIR):
	"""M >= 1 from the Prandtl-Meyer angle nu [rad]"""
	nu_max = float(np.real(prandtl_meyer_max(gamma)))
	_require(
		(np.real(nu) >= 0.0) & (np.real(nu) < nu_max),
		f"Prandtl-Meyer angle must be in [0, {nu_max:.5f}) rad",
	)

	return _solve_mach(
		prandtl_meyer_angle, _d_prandtl_meyer_angle,
		nu, gamma, 1.0, 2.0, grow=True,
	)
#endregion
