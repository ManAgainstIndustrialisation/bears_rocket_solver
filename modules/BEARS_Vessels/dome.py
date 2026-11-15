#region Imports
from math        import pi
from dataclasses import dataclass
from typing      import Protocol, runtime_checkable
#endregion

#region Constants
# Isotensoid dome factors
# kV: ratio of single-dome enclosed dome volume to cylinder radius cubed (V = kV * r^3)
# kL: ratio of dome depth along axis to cylinder radius (L = kL * r)
K_V_ISOTENSOID: float = 1.4341
K_L_ISOTENSOID: float = 0.6276

# Spherical (hemispherical) dome factors
K_V_SPHERICAL : float = (2.0 / 3.0) * pi
K_L_SPHERICAL : float = 1.0
#endregion

#region Functions
def dome_internal_volume(
	r_in : float,
	k_v  : float = K_V_ISOTENSOID,
) -> float:
	return k_v * r_in**3

def dome_length(
	r   : float,
	k_l : float = K_L_ISOTENSOID,
) -> float:
	return k_l * r

def dome_shell_volume(
	r_inner : float,
	r_outer : float,
	k_v     : float = K_V_ISOTENSOID,
) -> float:
	return k_v * (r_outer**3 - r_inner**3)
#endregion

#region Models
@runtime_checkable
class DomeGeometry(Protocol):
	"""Interface for vessel end-cap geometry models"""

	def internal_volume(self, r_in: float, r_boss: float = 0.0) -> float:
		...

	def total_length(self, r_in: float, r_boss: float = 0.0) -> float:
		...

	def shell_volume(
		self, r_inner: float, r_outer: float, r_boss: float = 0.0,
	) -> float:
		...

@dataclass(frozen=True)
class ConstantFactorDome:
	"""End-cap geometry parametrized by constant (k_v, k_l) factors"""
	k_v    : float
	k_l    : float
	n_caps : int = 2

	def internal_volume(self, r_in: float, r_boss: float = 0.0) -> float:
		return self.n_caps * dome_internal_volume(r_in, self.k_v)

	def total_length(self, r_in: float, r_boss: float = 0.0) -> float:
		return self.n_caps * dome_length(r_in, self.k_l)

	def shell_volume(
		self, r_inner: float, r_outer: float, r_boss: float = 0.0,
	) -> float:
		return self.n_caps * dome_shell_volume(r_inner, r_outer, self.k_v)

@dataclass(frozen=True)
class IsotensoidDome(ConstantFactorDome):
	"""Constant-factor geodesic isotensoid dome geometry"""
	k_v : float = K_V_ISOTENSOID
	k_l : float = K_L_ISOTENSOID

@dataclass(frozen=True)
class SphericalDome(ConstantFactorDome):
	"""Hemispherical end-cap geometry"""
	k_v : float = K_V_SPHERICAL
	k_l : float = K_L_SPHERICAL
#endregion
