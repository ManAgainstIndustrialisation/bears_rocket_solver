#region Imports
from dataclasses import dataclass
from typing      import Sequence

from openmdao.api import Problem
#endregion

#region Data structures
@dataclass(frozen=True)
class DiameterSweepPoint:
	diameter_m     : float  # Outer airframe diameter [m]
	l_ox_tank_m    : float  # Oxidizer tank length [m]
	l_press_tank_m : float  # Pressurant bottle length [m]
	l_fuel_m       : float  # Fuel grain length [m]
	l_nozzle_m     : float  # Nozzle divergent section length [m]
	l_prop_total_m : float  # Sum of the four lengths above [m]
	m_prop_kg      : float  # Burned propellant mass [kg]
	m_dry_kg       : float  # Dry mass [kg]
	apogee_m       : float  # 1D apogee [m]
	success        : bool   # Whether the optimizer converged
#endregion

#region Sweep
def sweep_diameters(prob: Problem) -> list[DiameterSweepPoint]:
	"""
	Re-optimize at each outer airframe diameter under [sweep] in the rocket
	inputs. The airframe wall thickness is held at its configured value, so
	the bore grows with the outer diameter. The tanks take the outer diameter
	"""
	d_inner_0 = prob.get_val("DesignVars.g_inner_diameter", units="m")[0]
	d_outer_0 = prob.get_val("DesignVars.g_outer_diameter", units="m")[0]
	wall      = d_outer_0 - d_inner_0

	prob.driver.opt_settings["disp"] = False

	results = []
	for d in prob.cfg.cfg_sweep.outer_diameters_m:
		prob.set_val("DesignVars.g_outer_diameter", d,        units="m")
		prob.set_val("DesignVars.g_inner_diameter", d - wall, units="m")
		prob.run()

		gv = lambda name: float(prob.get_val(name)[0])
		l_ox     = gv("Propulsion.tank_length")
		l_press  = gv("Propulsion.press_length")
		l_fuel   = gv("Propulsion.fuel_length")
		l_nozzle = gv("Propulsion.nozzle_length")

		results.append(DiameterSweepPoint(
			diameter_m     = d,
			l_ox_tank_m    = l_ox,
			l_press_tank_m = l_press,
			l_fuel_m       = l_fuel,
			l_nozzle_m     = l_nozzle,
			l_prop_total_m = l_ox + l_press + l_fuel + l_nozzle,
			m_prop_kg      = gv("OptimizationVars.o_propellant_mass"),
			m_dry_kg       = gv("Mass.dry_mass"),
			apogee_m       = gv("apogee"),
			success        = bool(prob.driver.result.success),
		))

	return results
#endregion

#region Formatting
def format_sweep_org_table(points: Sequence[DiameterSweepPoint]) -> str:
	header = (
		"| D_out [m] | L_ox [m] | L_press [m] | L_fuel [m] | L_nozzle [m] "
		"| L_tot [m] | M_prop [kg] | M_dry [kg] | Apogee [m] | Conv |"
	)

	lines = [header]
	for p in points:
		lines.append(
			f"| {p.diameter_m:9.3f} "
			f"| {p.l_ox_tank_m:8.4f} "
			f"| {p.l_press_tank_m:11.4f} "
			f"| {p.l_fuel_m:10.4f} "
			f"| {p.l_nozzle_m:12.4f} "
			f"| {p.l_prop_total_m:14.4f} "
			f"| {p.m_prop_kg:11.4f} "
			f"| {p.m_dry_kg:10.4f} "
			f"| {p.apogee_m:10.1f} "
			f"| {'Yes' if p.success else 'No':4} |"
		)
	return "\n".join(lines)
#endregion
