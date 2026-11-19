#region Imports
from dataclasses import fields
from pathlib     import Path

import tomllib

from .records import (
	MaterialConfig,
	GasConfig,
	LayerConfig,
	WallConfig,
	MaterialsConfig,
	FluidsConfig,
	GlobalConfig,
	TankConfig,
	InjectorConfig,
	FuelConfig,
	IgniterConfig,
	NozzleConfig,
	ModelsConfig,
	OptimizationSeedConfig,
	EfficienciesConfig,
	SpeciesConfig,
	BipropellantConfig,
	RocketConfig,
)

from .validation import (
	ConfigValidationError,
	validate_rocket_config,
	validate_bipropellant_config,
)
#endregion

#region Helpers
def deep_merge(base: dict, overlay: dict) -> dict:
	"""Recursively merge `overlay` into a copy of `base`"""
	merged = dict(base)
	for k, v in overlay.items():
		if (
			k in merged
			and isinstance(merged[k], dict)
			and isinstance(v, dict)
		):
			merged[k] = deep_merge(merged[k], v)
		else:
			merged[k] = v

	return merged

def build_section(cls, data: dict, section: str, **extra):
	"""
	Construct the config dataclass `cls` from the TOML table `data`

	Unknown keys are rejected so that stale or misspelled input entries are
	reported instead of being silently ignored
	"""
	allowed = {f.name for f in fields(cls)} - set(extra)
	unknown = sorted(set(data) - allowed)
	if unknown:
		raise ConfigValidationError(
			f"Unknown key(s) in [{section}]: {', '.join(unknown)}"
		)

	return cls(**data, **extra)
#endregion

#region Loaders
def load_configs(
	path         : str | Path | None = "inputs/rocket.toml",
	default_path : str | Path        = "inputs/rocket.default.toml",
	validate     : bool              = True,
) -> RocketConfig:
	with open(default_path, "rb") as f:
		data = tomllib.load(f)

	if path is not None:
		user_file = Path(path)

		if (
			user_file.exists()
			and user_file.resolve() != Path(default_path).resolve()
		):
			with open(user_file, "rb") as f:
				data = deep_merge(data, tomllib.load(f))

	cfg = RocketConfig(
		cfg_global       = build_section(GlobalConfig,   data["global"],           "global"),
		cfg_oxy_tank     = build_section(TankConfig,     data["oxidizer_tank"],    "oxidizer_tank"),
		cfg_press_tank   = build_section(TankConfig,     data["pressurizer_tank"], "pressurizer_tank"),
		cfg_injector     = build_section(InjectorConfig, data["injector"],         "injector"),
		cfg_fuel         = build_section(FuelConfig,     data["fuel"],             "fuel"),
		cfg_igniter      = build_section(IgniterConfig,  data.get("igniter", {}),  "igniter"),
		cfg_nozzle       = build_section(NozzleConfig,   data["nozzle"],           "nozzle"),
		cfg_models       = build_section(ModelsConfig,   data.get("models", {}),   "models"),
		cfg_optim        = build_section(
			OptimizationSeedConfig, data["optimization"], "optimization"
		),
		cfg_efficiencies = build_section(
			EfficienciesConfig, data.get("efficiencies", {}), "efficiencies"
		),
	)

	if validate: validate_rocket_config(cfg)

	return cfg

def load_reactants(
	path     : str | Path,
	validate : bool = True,
) -> BipropellantConfig:
	with open(path, "rb") as f:
		data = tomllib.load(f)

	def parse_entry(r: dict, role: str) -> SpeciesConfig:
		entry = dict(r)
		entry["formula_parts"] = tuple(entry.get("formula_parts", ()))
		return build_section(SpeciesConfig, entry, role, role=role)

	fuels = tuple(parse_entry(r, "fuel") for r in data["fuel"])
	oxids = tuple(parse_entry(r, "oxid") for r in data["oxid"])

	cfg = BipropellantConfig(fuels=fuels, oxidizers=oxids)

	if validate: validate_bipropellant_config(cfg)

	return cfg

def load_materials(path: str | Path) -> MaterialsConfig:
	with open(path, "rb") as f:
		data = tomllib.load(f)

	materials = []
	for m in data.get("material", []):
		rho = m["density"]
		if m.get("density_units") in ("g/cm^3", "g/cc", "g/cm3"):
			rho *= 1000.0

		ys = m["yield_strength"]
		us = m["ultimate_strength"]
		if m.get("strength_units") == "MPa":
			ys *= 1e6
			us *= 1e6

		em = m["elastic_modulus"]
		if m.get("modulus_units") == "GPa":
			em *= 1e9

		materials.append(MaterialConfig(
			id                = m["id"],
			name              = m["name"],
			density           = rho,
			yield_strength    = ys,
			ultimate_strength = us,
			elastic_modulus   = em,
		))

	walls = []
	for w in data.get("wall", []):
		layers = []
		for lay in w["layers"]:
			lay = dict(lay)
			material_id = lay.pop("material")
			layers.append(build_section(
				LayerConfig, lay, f"wall '{w['id']}' layer",
				material_id=material_id,
			))

		walls.append(WallConfig(id=w["id"], layers=tuple(layers)))

	return MaterialsConfig(materials=tuple(materials), walls=tuple(walls))

def load_fluids(path: str | Path) -> FluidsConfig:
	with open(path, "rb") as f:
		data = tomllib.load(f)

	gases = tuple(
		build_section(GasConfig, g, "gas") for g in data.get("gas", [])
	)

	return FluidsConfig(gases=gases)
#endregion
