#region Imports
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

	if gl.diameter_m <= 0:
		errors.append(f"global.diameter_m must be > 0 (got {gl.diameter_m})")

	if gl.clearance_m < 0:
		errors.append(f"global.clearance_m must be >= 0 (got {gl.clearance_m})")

	if ox.diam_m + 2 * gl.clearance_m > gl.diameter_m:
		errors.append(
			f"oxidizer_tank diameter ({ox.diam_m} m)"
			f" + clearance ({2 * gl.clearance_m} m) "
			f"exceeds airframe diameter ({gl.diameter_m} m)"
		)

	if pr.diam_m + 2 * gl.clearance_m > gl.diameter_m:
		errors.append(
			f"pressurizer_tank diameter ({pr.diam_m} m)"
			f" + clearance ({2 * gl.clearance_m} m) "
			f"exceeds airframe diameter ({gl.diameter_m} m)"
		)

	if ox.vapor_pressure_bar is None or ox.vapor_pressure_bar <= 0:
		errors.append(
			"oxidizer_tank.vapor_pressure_bar must be set and > 0 "
			f"(got {ox.vapor_pressure_bar})"
		)

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

	if nz.expansion_ratio <= 1.0 or nz.length_m <= 0:
		errors.append("invalid nozzle expansion ratio or length")

	if op.injector_area_m2 <= 0 or op.nozzle_throat_area_m2 <= 0:
		errors.append("optimization seed areas must be > 0")

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
