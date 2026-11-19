#region Imports
import numpy as np

from scipy.integrate import solve_ivp
from openmdao.api    import ExplicitComponent

from ..BEARS_Atmo import BEARS_Atm
from ..Config     import CONSTANTS
#endregion

g = CONSTANTS.universal.standard_gravity # Standard gravity [m/s^2]

#region Ballistic functions
def F_d(v: float, diam: float, rho: float, a: float) -> float:
	"""Drag force calculator"""

	area = np.pi * (diam / 2.0)**2.0
	mach = abs(v) / a

	# TODO: Better-founded C_d model, currently AI-generated
	if mach < 0.8:
		# Subsonic: skin friction, fins, base drag
		cd = 0.48
	elif mach < 1.2:
		# Transonic: drag increase due to shock wave
		cd = 0.48 + (mach - 0.8) * ( (0.85 - 0.48) / (1.2 - 0.8) )
	elif mach < 2.0:
		# Supersonic: drag decreases as Mach number increases
		cd = 0.85 + (mach - 1.2) * ( (0.85 - 0.65) / (2.0 - 1.2) )
	else:
		# High supersonic
		cd = 0.65

	drag = 0.5 * rho * v**2 * cd * area
	return drag

def ballistic_apogee(
	thrust : float,
	isp    : float,
	m_i    : float,
	m_prop : float,
	diam   : float,
	atm    : BEARS_Atm
) -> tuple[float, float]:
	"""
	Simple ballistic apogee calculator.

	We use a two-step boost+coast process with separate dynamics and integrators
	in order to avoid a sharp discontinuity in the integrator.
	"""
	mdot = thrust / (isp * g)
	t_burn = m_prop / mdot
	m_burnout = m_i - m_prop

	def dynamics_boost(t, y):
		h, v = y
		m = m_i - mdot * t

		_, _, rho, a = atm(max(0.0, h))
		f_net = thrust - F_d(v, diam, rho, a)

		if h <= 0.0 and f_net / m <= g:
			dh_dt, dv_dt = max(0.0, v), 0.0
		else:
			dh_dt, dv_dt = v, (f_net / m) - g

		return [dh_dt, dv_dt]

	def dynamics_coast(t, y):
		h, v = y

		_, _, rho, a = atm(max(0.0, h))

		dh_dt = v
		dv_dt = -F_d(v, diam, rho, a) / m_burnout - g
		return [dh_dt, dv_dt]

	# A SciPy integration event that captures the moment when velocity reaches 0
	def apogee_event(t, y): return y[1]
	apogee_event.terminal = True
	apogee_event.direction = -1

	# Integration steps
	sol_boost = solve_ivp(
		dynamics_boost,
		t_span=(0.0, t_burn),
		y0=[0.0, 0.0],
		method="RK45",
		rtol=1e-7,
		atol=1e-9,
	)

	h_burnout = sol_boost.y[0][-1]
	v_burnout = sol_boost.y[1][-1]

	sol_coast = solve_ivp(
		dynamics_coast,
		t_span=(0, 1000),
		y0=[h_burnout, v_burnout],
		method="RK45",
		rtol=1e-7,
		atol=1e-9,
		events=apogee_event,
	)

	apogee = sol_coast.y[0][-1]
	return t_burn, apogee
#endregion

class TrajectoryComponent(ExplicitComponent):

	def initialize(self):
		self.options.declare("atm", types=BEARS_Atm)

	def setup(self):
		# Propulsion profile
		self.add_input("thrust",          val=1000.0, units="N")
		self.add_input("isp",             val=200.0,  units="s")

		# Rocket parameters
		self.add_input("initial_mass",    val=15.0, units="kg")
		self.add_input("propellant_mass", val=5.0,  units="kg")
		self.add_input("diameter",        val=0.5,  units="m")

		self.add_output("apogee",         val=3000.0, units="m")
		self.add_output("burn_time",      val=3.0,    units="s")

	def setup_partials(self):
		self.declare_partials(
			"burn_time", ["thrust", "isp", "propellant_mass"]
		)

		self.declare_partials(
			"apogee",
			["thrust", "isp", "propellant_mass", "initial_mass", "diameter"],
			method="fd",
			step=1e-5,
		)

	def compute_partials(self, inputs, partials):
		thrust = inputs["thrust"][0]
		isp    = inputs["isp"][0]
		m_prop = inputs["propellant_mass"][0]

		# Provide exact partial derivatives:
		#
		#   t_burn = ( m_prop * isp * g ) / thrust
		#

		d_tburn_mprop = (isp * g) / thrust
		d_tburn_isp   = m_prop * g / thrust
		d_tburn_thr   = -( m_prop * isp * g ) / (thrust**2)

		partials["burn_time", "propellant_mass"] = d_tburn_mprop
		partials["burn_time", "isp"]             = d_tburn_isp
		partials["burn_time", "thrust"]          = d_tburn_thr

	def compute(self, inputs, outputs):
		atm = self.options["atm"]

		thrust = inputs["thrust"][0]
		isp    = inputs["isp"][0]
		m_i    = inputs["initial_mass"][0]
		m_prop = inputs["propellant_mass"][0]
		diam   = inputs["diameter"][0]

		burn_time, apogee = ballistic_apogee(
			thrust, isp, m_i, m_prop, diam, atm
		)

		outputs["burn_time"] = burn_time
		outputs["apogee"]    = apogee
