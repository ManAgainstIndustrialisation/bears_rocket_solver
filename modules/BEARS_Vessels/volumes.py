#region Imports
import numpy as np
#endregion

#region Helpers
def _check_ullage_fraction(ullage_frac: float | complex) -> None:
	u_val = ullage_frac.real if np.iscomplexobj(ullage_frac) else ullage_frac
	if u_val < 0.0 or u_val >= 1.0:
		raise ValueError(f"Ullage fraction must be in [0, 1), got {u_val}")

def tank_internal_volume(
	v_fluid     : float | complex,
	ullage_frac : float | complex,
) -> float | complex:
	"""Total internal tank volume for tank-volume ullage fraction `u`"""
	_check_ullage_fraction(ullage_frac)
	return v_fluid / (1.0 - ullage_frac)

def ullage_volume(
	v_fluid     : float | complex,
	ullage_frac : float | complex,
) -> float | complex:
	"""Initial ullage volume matching `V_ullage = u * V_tank`"""
	return ullage_frac * tank_internal_volume(v_fluid, ullage_frac)
#endregion
