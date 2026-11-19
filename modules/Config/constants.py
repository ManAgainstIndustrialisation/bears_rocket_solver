"""
Physical constants, loaded from `inputs/constants.toml`

The code holds no physical constants of its own. Everything reads them from
the `CONSTANTS` instance below, which is loaded once on import
"""

#region Imports
from dataclasses import dataclass, fields
from pathlib     import Path

import tomllib
#endregion

DEFAULT_CONSTANTS_PATH = Path(__file__).resolve().parents[2] / "inputs" / "constants.toml"

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
class AirProperties:
	molar_mass : float  # [kg/mol]
	gamma      : float  # cp / cv
	r_specific : float  # R / M [J/(kg*K)], derived on load

@dataclass(frozen=True)
class PhysicalConstants:
	universal  : UniversalConstants
	reference  : ReferenceState
	atmosphere : StandardAtmosphere
	air        : AirProperties
#endregion

#region Loader
def _build(cls, data: dict, section: str, **derived):
	"""Construct `cls` from a TOML table, rejecting unknown and missing keys"""
	table    = data.get(section, {})
	expected = {f.name for f in fields(cls)} - set(derived)

	unknown = sorted(set(table) - expected)
	missing = sorted(expected - set(table))
	if unknown or missing:
		problems = []
		if unknown: problems.append(f"unknown key(s) {', '.join(unknown)}")
		if missing: problems.append(f"missing key(s) {', '.join(missing)}")
		raise ValueError(f"[{section}] in constants file: {'; '.join(problems)}")

	return cls(**table, **derived)

def load_constants(path: str | Path = DEFAULT_CONSTANTS_PATH) -> PhysicalConstants:
	with open(path, "rb") as f:
		data = tomllib.load(f)

	universal = _build(UniversalConstants, data, "universal")

	# Specific gas constant of air, R / M. A missing molar mass is reported
	# by `_build` below
	air_molar = data.get("air", {}).get("molar_mass")
	r_air     = universal.molar_gas_constant / air_molar if air_molar else None

	return PhysicalConstants(
		universal  = universal,
		reference  = _build(ReferenceState,     data, "reference"),
		atmosphere = _build(StandardAtmosphere, data, "atmosphere"),
		air        = _build(AirProperties,      data, "air", r_specific=r_air),
	)
#endregion

CONSTANTS = load_constants()
