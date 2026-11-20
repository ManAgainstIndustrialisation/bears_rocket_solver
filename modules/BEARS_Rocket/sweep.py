#region Imports
from dataclasses import dataclass
from typing import Sequence
from openmdao.api import Problem
#endregion

#region Data structures
@dataclass(frozen=True)
class DiameterSweepPoint:
	diameter_m     : float
	l_ox_tank_m    : float
	l_press_tank_m : float
	l_fuel_m       : float
	l_nozzle_m     : float
	l_prop_total_m : float
	m_prop_kg      : float
	m_dry_kg       : float
	apogee_m       : float
	success        : bool
#endregion

#region Sweep
def sweep_diameters(
	prob        : Problem,
	diameters_m : Sequence[float],
	quiet       : bool = True,
) -> list[DiameterSweepPoint]:
	"""
	Re-optimize over a range of outer airframe diameters. The airframe wall
	thickness is held at its configured value, so the bore and the tanks grow
	with the outer diameter
	"""
	results = []
	clearance = prob.get_val("DesignVars.g_clearance", units="m")[0]
	d_inner_0 = prob.get_val("DesignVars.g_inner_diameter", units="m")[0]
	d_outer_0 = prob.get_val("DesignVars.g_outer_diameter", units="m")[0]
	wall      = d_outer_0 - d_inner_0

	for d in diameters_m:
		d_inner = d - wall
		d_tank  = d_inner - 2.0 * clearance

		prob.set_val("DesignVars.g_outer_diameter", d,       units="m")
		prob.set_val("DesignVars.g_inner_diameter", d_inner, units="m")
		prob.set_val("DesignVars.tank_diam",        d_tank,  units="m")
		prob.set_val("DesignVars.press_diam",       d_tank,  units="m")

		if quiet: prob.driver.opt_settings["disp"] = False

		prob.run()

		gv = lambda name: float(prob.get_val(name)[0])
		l_ox     = gv("Propulsion.tank_length")
		l_press  = gv("Propulsion.press_length")
		l_fuel   = gv("Propulsion.fuel_length")
		l_nozzle = gv("Propulsion.nozzle_length")
		l_tot    = l_ox + l_press + l_fuel + l_nozzle

		m_prop  = gv("OptimizationVars.o_propellant_mass")
		m_dry   = gv("Mass.dry_mass")
		apogee  = gv("apogee")
		success = bool(prob.driver.result.success)

		results.append(
			DiameterSweepPoint(
				diameter_m     = d,
				l_ox_tank_m    = l_ox,
				l_press_tank_m = l_press,
				l_fuel_m       = l_fuel,
				l_nozzle_m     = l_nozzle,
				l_prop_total_m = l_tot,
				m_prop_kg      = m_prop,
				m_dry_kg       = m_dry,
				apogee_m       = apogee,
				success        = success,
			)
		)

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
