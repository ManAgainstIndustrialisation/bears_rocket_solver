"""
Physical constants, loaded from `inputs/constants.toml`, and the properties of
air, loaded from `inputs/materials.toml`

The code holds no physical constants or material properties of its own.
Everything reads them from the `CONSTANTS` and `AIR` instances below, which
are loaded once on import. The other material, fluid and reactant tables in
`materials.toml` have their own loaders in `loader.py`
"""

#region Imports
from dataclasses import dataclass, fields
from pathlib     import Path

import tomllib
#endregion

INPUTS_DIR             = Path(__file__).resolve().parents[2] / "inputs"
DEFAULT_CONSTANTS_PATH = INPUTS_DIR / "constants.toml"
DEFAULT_MATERIALS_PATH = INPUTS_DIR / "materials.toml"

#region Data structures
@dataclass(frozen=True)
class UniversalConstants:
	standard_gravity   : float  # g0 [m/s^2]
	molar_gas_constant : float  # R [J/(mol*K)]
	zero_celsius       : float  # 0 degC [K]

@dataclass(frozen=True)
class ReferenceState:
	temperature : float  # Thermochemical reference temperature [K]

@dataclass(frozen=True)
class StandardAtmosphere:
	sea_level_pressure     : float  # [Pa]
	sea_level_temperature  : float  # [K]
	lapse_rate             : float  # [K/m]
	tropopause_temperature : float  # [K]

@dataclass(frozen=True)
class PhysicalConstants:
	universal    : UniversalConstants
	reference    : ReferenceState
	atmosphere   : StandardAtmosphere

@dataclass(frozen=True)
class AirProperties:
	molar_mass : float  # [kg/mol]
	gamma      : float  # cp / cv
	r_specific : float  # R / M [J/(kg*K)], derived on load
#endregion

#region Loaders
def _build(cls, data: dict, section: str, file: str, **derived):
	"""Construct `cls` from a TOML table, rejecting unknown and missing keys"""
	table    = data.get(section, {})
	expected = {f.name for f in fields(cls)} - set(derived)

	unknown = sorted(set(table) - expected)
	missing = sorted(expected - set(table))
	if unknown or missing:
		problems = []
		if unknown: problems.append(f"unknown key(s) {', '.join(unknown)}")
		if missing: problems.append(f"missing key(s) {', '.join(missing)}")
		raise ValueError(f"[{section}] in {file}: {'; '.join(problems)}")

	return cls(**table, **derived)

def load_constants(path: str | Path = DEFAULT_CONSTANTS_PATH) -> PhysicalConstants:
	path = Path(path)
	with open(path, "rb") as f:
		data = tomllib.load(f)

	return PhysicalConstants(
		universal  = _build(UniversalConstants, data, "universal",  path.name),
		reference  = _build(ReferenceState,     data, "reference",  path.name),
		atmosphere = _build(StandardAtmosphere, data, "atmosphere", path.name),
	)

def load_air(
	path      : str | Path               = DEFAULT_MATERIALS_PATH,
	constants : PhysicalConstants | None = None,
) -> AirProperties:
	path = Path(path)
	with open(path, "rb") as f:
		data = tomllib.load(f)

	if constants is None: constants = CONSTANTS

	# Specific gas constant of air, R / M. A missing molar mass is reported
	# by `_build` below
	molar = data.get("air", {}).get("molar_mass")
	r_air = constants.universal.molar_gas_constant / molar if molar else None

	return _build(AirProperties, data, "air", path.name, r_specific=r_air)
#endregion

CONSTANTS = load_constants()
AIR       = load_air()
