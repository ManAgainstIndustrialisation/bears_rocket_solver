#region Imports
from typing       import Callable, Literal, NamedTuple
from openmdao.api import Problem

from ..Config import CONSTANTS
#endregion

g = CONSTANTS.universal.standard_gravity # Standard gravity [m/s^2]

#region Types
class CheckResult(NamedTuple):
	severity : Literal["error", "warning"]
	message  : str

CheckFn = Callable[[Problem], tuple[CheckResult, ...]]
#endregion

#region Flight Checks
def check_injector_dp(prob: Problem) -> tuple[CheckResult, ...]:
	issues: list[CheckResult] = []
	dp = prob.get_val("Propulsion.injector_delta_p",      units="bar")[0]
	pc = prob.get_val("Propulsion.prop_chamber_pressure", units="bar")[0]

	if dp <= 0.0:
		issues.append(CheckResult(
			"error",
			f"Injector ΔP non-positive ({dp:.3f} bar)"
		))
	elif dp / pc < 0.15:
		ratio = dp / pc
		issues.append(CheckResult(
			"warning",
			f"Injector ΔP ratio low ({ratio:.1%})"
		))

	return tuple(issues)

def check_liftoff_twr(prob: Problem) -> tuple[CheckResult, ...]:
	issues: list[CheckResult] = []
	thr = prob.get_val("Propulsion.prop_thrust", units="N")[0]
	mi  = prob.get_val("Mass.initial_mass",      units="kg")[0]
	twr = thr / (mi * g)

	if twr < 1.0:
		issues.append(CheckResult(
			"error",
			f"Liftoff TWR below 1.0 ({twr:.3f})"
		))
	elif twr < 1.3:
		issues.append(CheckResult(
			"warning",
			f"Liftoff TWR is low ({twr:.3f})"
		))

	return tuple(issues)

def check_nozzle_exit_diameter(prob: Problem) -> tuple[CheckResult, ...]:
	"""The nozzle is part of the engine, so it has to fit the airframe bore"""
	d_exit = prob.get_val("DesignVars.nozzle_exit_diam", units="m")[0]
	d_bore = prob.get_val("DesignVars.g_inner_diameter", units="m")[0]

	if d_exit > d_bore:
		return (CheckResult(
			"warning",
			f"Nozzle exit diameter ({d_exit * 1e3:.1f} mm) is larger than the "
			f"rocket inner diameter ({d_bore * 1e3:.1f} mm)"
		),)

	return ()

def check_fuel_grain_diameter(prob: Problem) -> tuple[CheckResult, ...]:
	"""The fuel grain has to fit the airframe bore"""
	d_grain = prob.get_val("Propulsion.fuel_grain_diam",  units="m")[0]
	d_bore  = prob.get_val("DesignVars.g_inner_diameter", units="m")[0]

	if d_grain > d_bore:
		return (CheckResult(
			"error",
			f"Fuel grain diameter ({d_grain * 1e3:.1f} mm) is larger than the "
			f"rocket inner diameter ({d_bore * 1e3:.1f} mm)"
		),)

	return ()

def check_engine_targets(prob: Problem) -> tuple[CheckResult, ...]:
	"""The optimized engine must deliver the target thrust and chamber pressure"""
	issues: list[CheckResult] = []

	targets = (
		("Thrust",           "Propulsion.prop_thrust",           "DesignVars.g_target_thrust",           "N"),
		("Chamber pressure", "Propulsion.prop_chamber_pressure", "DesignVars.g_target_chamber_pressure", "bar"),
	)

	for label, name, target_name, units in targets:
		val    = prob.get_val(name,        units=units)[0]
		target = prob.get_val(target_name, units=units)[0]
		if abs(val - target) > 1e-2 * target:
			issues.append(CheckResult(
				"error",
				f"{label} ({val:.3f} {units}) misses its target ({target:.3f} {units})"
			))

	return tuple(issues)

def check_mass_balance(prob: Problem) -> tuple[CheckResult, ...]:
	mi    = prob.get_val("Mass.initial_mass",                  units="kg")[0]
	mdry  = prob.get_val("Mass.dry_mass",                      units="kg")[0]
	mprop = prob.get_val("OptimizationVars.o_propellant_mass", units="kg")[0]
	mpr   = prob.get_val("Mass.pressurant_mass",               units="kg")[0]

	mcalc = mdry + mprop + mpr

	if abs(mi - mcalc) > 1e-3:
		return (CheckResult(
			"error",
			f"Mass balance mismatch: {mi:.3f} kg != {mcalc:.3f} kg"
		),)

	return ()

def check_target_apogee(prob: Problem) -> tuple[CheckResult, ...]:
	ap     = prob.get_val("Trajectory.apogee",            units="m")[0]
	target = prob.get_val("DesignVars.g_target_altitude", units="m")[0]

	eta_t = prob.get_val("EfficiencyVars.eta_trajectory")[0]
	ap_3d = ap * eta_t
	err = abs(ap_3d - target)

	if err > 20.0:
		return (CheckResult(
			"error",
			f"Apogee target error is {err:.2f} m"
		),)

	return ()

def check_combustion_isp(prob: Problem) -> tuple[CheckResult, ...]:
	isp = prob.get_val("Propulsion.prop_isp", units="s")[0]

	if not (150.0 <= isp <= 350.0):
		return (CheckResult(
			"warning",
			f"Isp ({isp:.1f} s) outside range [150, 350]"
		),)

	return ()

def check_igniter_margin(prob: Problem) -> tuple[CheckResult, ...]:
	margin = prob.get_val("Propulsion.igniter_thermal_margin")[0]
	if margin < 2.0:
		return (CheckResult(
			"warning",
			f"Igniter thermal margin ({margin:.1f}x) below 2.0x threshold"
		),)

	return ()

def check_igniter_port_clearance(prob: Problem) -> tuple[CheckResult, ...]:
	blockage = prob.get_val("Propulsion.igniter_port_blockage")[0]
	if blockage >= 0.20:
		return (CheckResult(
			"warning",
			f"Igniter port blockage ({blockage * 100:.1f}%) exceeds 20%"
		),)

	return ()

def check_flame_temperature(prob: Problem) -> tuple[CheckResult, ...]:
	tc = prob.get_val("Propulsion.prop_chamber_temp", units="K")[0]

	if not (1500.0 <= tc <= 4000.0):
		return (CheckResult(
			"warning",
			f"Flame temperature ({tc:.3f} K) outside range [1500, 4000]"
		),)

	return ()
#endregion

#region Suites and Runner
DEFAULT_ROCKET_CHECKS: tuple[CheckFn, ...] = (
	check_injector_dp,
	check_liftoff_twr,
	check_nozzle_exit_diameter,
	check_fuel_grain_diameter,
	check_engine_targets,
	check_mass_balance,
	check_target_apogee,
	check_combustion_isp,
	#check_igniter_margin,
	#check_igniter_port_clearance,
	#check_flame_temperature,
)

def run_checks(
	prob           : Problem,
	checks         : tuple[CheckFn, ...],
	raise_on_error : bool = True,
) -> tuple[CheckResult, ...]:
	results: list[CheckResult] = []
	for check in checks:
		results.extend(check(prob))

	errors   = [r.message for r in results if r.severity == "error"]
	warnings = [r.message for r in results if r.severity == "warning"]

	if raise_on_error and errors:
		msg = "\n  - ".join(errors)
		raise ValueError(f"Run verification failed:\n  - {msg}")

	for w in warnings:
		print(f"Warning: {w}")

	return tuple(results)
#endregion
