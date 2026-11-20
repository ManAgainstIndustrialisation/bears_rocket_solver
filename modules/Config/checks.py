"""
Acceptance limits for the optimized rocket, loaded from `inputs/checks.toml`
"""

#region Imports
from dataclasses import dataclass
from pathlib     import Path

import tomllib

from .constants  import INPUTS_DIR
from .validation import build, require, require_positive
#endregion

@dataclass(frozen=True)
class ChecksConfig:
	min_injector_pressure_drop_ratio : float  # Warn below this injector pressure drop over chamber pressure [-]
	min_liftoff_twr                  : float  # Fail below this liftoff thrust-to-weight ratio [-]
	low_liftoff_twr                  : float  # Warn below this liftoff thrust-to-weight ratio [-]
	min_isp_s                        : float  # Warn below this delivered Isp [s]
	max_isp_s                        : float  # Warn above this delivered Isp [s]
	min_flame_temperature_k          : float  # Warn below this chamber temperature [K]
	max_flame_temperature_k          : float  # Warn above this chamber temperature [K]
	apogee_tolerance_m               : float  # Fail when the apogee misses its target by more [m]
	target_tolerance                 : float  # Fail when thrust or chamber pressure misses its target by more, relative [-]

	def __post_init__(self):
		require_positive(
			self, "min_injector_pressure_drop_ratio", "min_liftoff_twr", "min_isp_s",
			"min_flame_temperature_k", "apogee_tolerance_m", "target_tolerance",
		)
		require(self.low_liftoff_twr >= self.min_liftoff_twr,                "checks: low_liftoff_twr must be >= min_liftoff_twr")
		require(self.max_isp_s > self.min_isp_s,                             "checks: max_isp_s must exceed min_isp_s")
		require(self.max_flame_temperature_k > self.min_flame_temperature_k, "checks: max_flame_temperature_k must exceed min_flame_temperature_k")

def load_checks(path: str | Path = INPUTS_DIR / "checks.toml") -> ChecksConfig:
	with open(path, "rb") as f:
		return build(ChecksConfig, tomllib.load(f), "checks file")
