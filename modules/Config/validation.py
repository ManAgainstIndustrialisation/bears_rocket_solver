#region Imports
from math import pi

from .records import RocketConfig, BipropellantConfig, SpeciesConfig
#endregion

class ConfigValidationError(ValueError):
	"""Raised when config values violate physical constraints"""
	pass

def validate_species_config(
	sp      : SpeciesConfig,
	context : str = "",
) -> list[str]:
	errors = []
	prefix = f"{context}: " if context else ""

	if not sp.name or not sp.name.strip():
		errors.append(f"{prefix}species name cannot be empty")

	if sp.mass_fraction <= 0:
		errors.append(f"{prefix}mass_fraction must be > 0 (got {sp.mass_fraction})")

	if sp.temperature_k <= 0:
		errors.append(f"{prefix}temperature_k must be > 0 (got {sp.temperature_k})")

	if sp.density is not None and sp.density <= 0:
		errors.append(f"{prefix}density must be > 0 (got {sp.density})")

	if sp.vapor_pressure_bar is not None and sp.vapor_pressure_bar <= 0:
		errors.append(
			f"{prefix}vapor_pressure_bar must be > 0 (got {sp.vapor_pressure_bar})"
		)

	return errors

def validate_bipropellant_config(cfg: BipropellantConfig) -> None:
	errors = []

	if not cfg.fuels:
		errors.append("fuels list cannot be empty")

	if not cfg.oxidizers:
		errors.append("oxidizers list cannot be empty")

	for f in cfg.fuels:
		errors.extend(validate_species_config(f, f"Fuel '{f.name}'"))

	for o in cfg.oxidizers:
		errors.extend(validate_species_config(o, f"Oxidizer '{o.name}'"))

	if errors:
		raise ConfigValidationError(
			"Invalid BipropellantConfig:\n  - " + "\n  - ".join(errors)
		)

def validate_rocket_config(cfg: RocketConfig) -> None:
	errors = []
	gl = cfg.cfg_global
	ox = cfg.cfg_oxy_tank
	pr = cfg.cfg_press_tank

	if gl.non_propulsion_mass_kg < 0:
		errors.append(
			f"global.non_propulsion_mass_kg must be >= 0 (got {gl.non_propulsion_mass_kg})"
		)

	if gl.target_thrust_N <= 0:
		errors.append(f"global.target_thrust_N must be > 0 (got {gl.target_thrust_N})")

	if gl.target_chamber_pressure_bar <= 0:
		errors.append(
			"global.target_chamber_pressure_bar must be > 0 "
			f"(got {gl.target_chamber_pressure_bar})"
		)

	# The injector needs a positive pressure drop to feed the chamber
	if gl.target_chamber_pressure_bar >= ox.pressure_bar:
		errors.append(
			f"global.target_chamber_pressure_bar ({gl.target_chamber_pressure_bar} bar) "
			f"must be below oxidizer_tank.pressure_bar ({ox.pressure_bar} bar)"
		)

	if gl.inner_rocket_diameter_m <= 0:
		errors.append(
			f"global.inner_rocket_diameter_m must be > 0 (got {gl.inner_rocket_diameter_m})"
		)

	if gl.inner_rocket_diameter_m > gl.outer_rocket_diameter_m:
		errors.append(
			f"global.inner_rocket_diameter_m ({gl.inner_rocket_diameter_m} m) exceeds "
			f"global.outer_rocket_diameter_m ({gl.outer_rocket_diameter_m} m)"
		)

	if gl.clearance_m < 0:
		errors.append(f"global.clearance_m must be >= 0 (got {gl.clearance_m})")

	# The tanks sit inside the airframe bore
	if ox.diam_m + 2 * gl.clearance_m > gl.inner_rocket_diameter_m:
		errors.append(
			f"oxidizer_tank diameter ({ox.diam_m} m)"
			f" + clearance ({2 * gl.clearance_m} m) "
			f"exceeds inner airframe diameter ({gl.inner_rocket_diameter_m} m)"
		)

	if pr.diam_m + 2 * gl.clearance_m > gl.inner_rocket_diameter_m:
		errors.append(
			f"pressurizer_tank diameter ({pr.diam_m} m)"
			f" + clearance ({2 * gl.clearance_m} m) "
			f"exceeds inner airframe diameter ({gl.inner_rocket_diameter_m} m)"
		)

	# Drag table
	aero = cfg.cfg_aero
	if not aero.drag_mach or len(aero.drag_mach) != len(aero.drag_cd):
		errors.append("aerodynamics.drag_mach and drag_cd need the same, nonzero length")

	if any(b <= a for a, b in zip(aero.drag_mach, aero.drag_mach[1:])):
		errors.append("aerodynamics.drag_mach must be strictly increasing")

	if any(cd < 0 for cd in aero.drag_cd):
		errors.append("aerodynamics.drag_cd must be >= 0")

	# Pressure hierarchy
	if pr.pressure_bar <= ox.pressure_bar:
		errors.append(
			f"pressurizer pressure ({pr.pressure_bar} bar) must exceed "
			f"oxidizer pressure ({ox.pressure_bar} bar)"
		)

	if ox.pressure_bar <= 0:
		errors.append(f"oxidizer_tank.pressure_bar must be > 0 (got {ox.pressure_bar})")

	if ox.safety_factor < 1.0 or pr.safety_factor < 1.0:
		errors.append("tank safety factors must be >= 1.0")

	if not (0.0 <= ox.ullage_fraction < 1.0):
		errors.append("oxidizer_tank.ullage_fraction must be in [0.0, 1.0)")

	# Engine and nozzle
	inj = cfg.cfg_injector
	nz  = cfg.cfg_nozzle
	op  = cfg.cfg_optim

	if not (0.0 < inj.cd <= 1.0):
		errors.append("injector.cd must be in (0.0, 1.0]")

	if nz.nozzle_exit_diameter_m <= 0:
		errors.append(
			f"nozzle.nozzle_exit_diameter_m must be > 0 (got {nz.nozzle_exit_diameter_m})"
		)

	if not (0.0 < nz.conical_nozzle_half_angle_deg < 90.0):
		errors.append(
			"nozzle.conical_nozzle_half_angle_deg must be in (0, 90) "
			f"(got {nz.conical_nozzle_half_angle_deg})"
		)

	if op.injector_area_m2 <= 0 or op.nozzle_throat_area_m2 <= 0:
		errors.append("optimization seed areas must be > 0")

	# The expansion ratio A_exit / A_throat must exceed 1 at the seed
	a_exit = pi / 4.0 * nz.nozzle_exit_diameter_m**2
	if op.nozzle_throat_area_m2 >= a_exit:
		errors.append(
			f"optimization.nozzle_throat_area_m2 ({op.nozzle_throat_area_m2:g} m^2) "
			f"must be below the nozzle exit area ({a_exit:g} m^2)"
		)

	model_choices = {
		"atmosphere"        : ("auto", "isacalc", "standalone"),
		"chemistry"         : ("auto", "cea", "rocketcea"),
		"pressurant_thermo" : ("auto", "coolprop", "ideal"),
	}
	for field_name, allowed in model_choices.items():
		val = getattr(cfg.cfg_models, field_name)
		if val not in allowed:
			opts = ", ".join(f"'{a}'" for a in allowed)
			errors.append(
				f"models.{field_name} must be ({opts}), got '{val}'"
			)

	if errors:
		raise ConfigValidationError(
			"Invalid RocketConfig:\n  - " + "\n  - ".join(errors)
		)
