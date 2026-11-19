#region Imports
from dataclasses import dataclass
from typing      import Protocol, runtime_checkable

import numpy as np

from ..BEARS_Materials import Gas
from ..BEARS_Vessels   import ullage_volume
#endregion

#region Blowdown results
@dataclass(frozen=True)
class BlowdownResult:
	"""Pressurant blowdown sizing outputs in base SI units"""
	m_press     : float | complex
	rho_press   : float | complex
	m_pad       : float | complex
	m_burn      : float | complex
	f_delivered : float | complex

@runtime_checkable
class PressurantThermoModel(Protocol):
	"""Thermodynamic backend interface for pressurant blowdown"""
	supports_complex_step: bool

	def compute(
		self,
		gas      : Gas,
		p_bottle : float | complex,
		p_ox     : float | complex,
		p_margin : float | complex,
		p_sat    : float | complex,
		t0       : float | complex,
		v_ox     : float | complex,
		u_frac   : float | complex,
	) -> BlowdownResult: ...
#endregion

def _pos_pad(p_ox, p_sat):
	diff = p_ox - p_sat
	if np.iscomplexobj(diff):
		return diff if diff.real > 0.0 else 0.0
	return max(0.0, diff)

#region Models
@dataclass(frozen=True)
class IdealGasBlowdown:
	"""Isentropic ideal-gas blowdown with fixed bottle Z"""
	safety_factor         : float = 1.10
	supports_complex_step : bool  = True

	def compute(
		self, gas: Gas, p_bottle, p_ox, p_margin, p_sat, t0, v_ox, u_frac,
	) -> BlowdownResult:
		r, g = gas.r_specific, gas.gamma
		v_u0 = ullage_volume(v_ox, u_frac)
		m_pad = _pos_pad(p_ox, p_sat) * v_u0 / (r * t0)
		pr = (p_ox + p_margin) / p_bottle
		f_del = 1.0 - pr ** (1.0 / g)
		t_mean = (t0 / g) * (1.0 - pr) / f_del
		m_burn = (p_ox * v_ox) / (r * t_mean)
		m_press = self.safety_factor * (m_burn + m_pad) / f_del
		rho = p_bottle / (gas.z_factor * r * t0)
		return BlowdownResult(m_press, rho, m_pad, m_burn, f_del)

@dataclass(frozen=True)
class CoolPropBlowdown:
	"""Real-gas CoolProp blowdown backend"""
	n_steps               : int   = 40
	safety_factor         : float = 1.10
	use_coolprop_psat     : bool  = False
	oxidizer              : str   = "N2O"
	supports_complex_step : bool  = False

	def compute(
		self, gas: Gas, p_bottle, p_ox, p_margin, p_sat, t0, v_ox, u_frac,
	) -> BlowdownResult:
		from CoolProp.CoolProp import PropsSI
		from scipy.optimize    import brentq

		fl = gas.coolprop_name or gas.name
		t0_f,   p_b_f  = float(t0), float(p_bottle)
		p_ox_f, v_ox_f = float(p_ox), float(v_ox)
		p_end = p_ox_f + float(p_margin)

		rho0  = PropsSI("D", "T", t0_f, "P", p_b_f, fl)
		s0    = PropsSI("S", "T", t0_f, "P", p_b_f, fl)
		ps    = np.linspace(p_b_f, p_end, self.n_steps)
		rhos  = np.array([PropsSI("D", "P", p, "S", s0, fl) for p in ps])
		hs    = np.array([PropsSI("H", "P", p, "S", s0, fl) for p in ps])
		dm    = rhos[:-1] - rhos[1:]
		h_in  = float(np.sum(0.5 * (hs[:-1] + hs[1:]) * dm) / np.sum(dm))
		f_del = float(1.0 - rhos[-1] / rho0)

		v_u0 = ullage_volume(v_ox_f, u_frac)
		v_u1 = v_u0 + v_ox_f
		rho1 = PropsSI("D", "T", t0_f, "P", p_ox_f, fl)
		u1   = PropsSI("U", "T", t0_f, "P", p_ox_f, fl)
		m1   = rho1 * v_u0

		def res(temp):
			rho2 = PropsSI("D", "T", temp, "P", p_ox_f, fl)
			u2   = PropsSI("U", "T", temp, "P", p_ox_f, fl)
			m2   = rho2 * v_u1
			rhs  = m1 * u1 + (m2 - m1) * h_in - p_ox_f * v_ox_f
			return m2 * u2 - rhs

		t2 = brentq(res, 150.0, t0_f * 1.5)

		m_burn = PropsSI("D", "T", t2, "P", p_ox_f, fl) * v_u1 - m1
		if self.use_coolprop_psat:
			p_sat = PropsSI("P", "T", t0_f, "Q", 0, self.oxidizer)
		m_pad = _pos_pad(p_ox_f, float(p_sat)) * v_u0 / (gas.r_specific * t0_f)
		m_press = self.safety_factor * (m_burn + m_pad) / f_del
		return BlowdownResult(m_press, rho0, m_pad, m_burn, f_del)

def create_pressurant_thermo(
	backend: str = "auto",
	use_coolprop_psat: bool = False,
	**kw,
) -> PressurantThermoModel:
	"""Instantiate a pressurant blowdown thermodynamics backend"""
	from importlib.util import find_spec
	match backend:
		case "auto":
			if find_spec("CoolProp") is not None:
				return CoolPropBlowdown(
					use_coolprop_psat=use_coolprop_psat, **kw
				)
			return IdealGasBlowdown(**kw)
		case "coolprop":
			return CoolPropBlowdown(
				use_coolprop_psat=use_coolprop_psat, **kw
			)
		case "ideal":
			return IdealGasBlowdown(**kw)
		case _:
			raise ValueError(f"Unknown pressurant thermo backend: {backend}")
#endregion
