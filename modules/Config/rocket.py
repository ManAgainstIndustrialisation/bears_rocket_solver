"""
Rocket design inputs, loaded from `inputs/rocket_inputs.toml`

Each record mirrors one section of the input file and checks its own values.
`RocketConfig` checks the rules that span several sections
"""

#region Imports
from dataclasses import dataclass, fields
from math        import pi
from pathlib     import Path

import tomllib

from .constants  import CONSTANTS, INPUTS_DIR
from .validation import build, check_keys, require, require_positive
#endregion

#region Vehicle
@dataclass(frozen=True)
class GlobalConfig:
	non_propulsion_mass_kg      : float  # Everything but the propulsion system, payload included [kg]
	engine_dry_mass_kg          : float  # Engine hardware without propellant: injector, chamber, nozzle [kg]
	target_altitude_m           : float  # Apogee the rocket has to reach [m]
	target_thrust_N             : float  # Liftoff thrust the engine is sized for [N]
	target_chamber_pressure_bar : float  # Chamber pressure the engine is sized for [bar]
	inner_rocket_diameter_m     : float  # Airframe bore, the engine has to fit inside it [m]
	outer_rocket_diameter_m     : float  # Airframe skin: the tank diameter and the drag reference [m]

	def __post_init__(self):
		require_positive(
			self, "non_propulsion_mass_kg", "engine_dry_mass_kg", "target_altitude_m",
			"target_thrust_N", "target_chamber_pressure_bar",
			"inner_rocket_diameter_m", "outer_rocket_diameter_m",
		)
		require(
			self.inner_rocket_diameter_m < self.outer_rocket_diameter_m,
			"[global] inner_rocket_diameter_m must be below outer_rocket_diameter_m",
		)

@dataclass(frozen=True)
class AerodynamicsConfig:
	drag_mach : tuple[float, ...]  # Mach numbers of the drag table, increasing [-]
	drag_cd   : tuple[float, ...]  # Drag coefficient at each Mach number [-]

	def __post_init__(self):
		require(
			len(self.drag_mach) > 0 and len(self.drag_mach) == len(self.drag_cd),
			"[aerodynamics] drag_mach and drag_cd need the same, nonzero length",
		)
		require(
			all(b > a for a, b in zip(self.drag_mach, self.drag_mach[1:])),
			"[aerodynamics] drag_mach must be strictly increasing",
		)
		require(all(cd > 0 for cd in self.drag_cd), "[aerodynamics] drag_cd must be > 0")
#endregion

#region Tanks
@dataclass(frozen=True)
class OxidizerTankConfig:
	wall              : str    # Wall layup id from the materials file
	pressure_bar      : float  # Maximum operating pressure [bar]
	safety_factor     : float  # Burst pressure over operating pressure [-]
	ullage_fraction   : float  # Gas-filled share of the tank volume at loading [-]
	boss_length_fwd_m : float  # Forward boss fitting length [m]
	boss_length_aft_m : float  # Aft boss fitting length [m]

	def __post_init__(self):
		require_positive(self, "pressure_bar")
		require(self.safety_factor >= 1.0,          "[oxidizer_tank] safety_factor must be >= 1")
		require(0.0 <= self.ullage_fraction < 1.0,  "[oxidizer_tank] ullage_fraction must be in [0, 1)")
		require(self.boss_length_fwd_m >= 0.0,      "[oxidizer_tank] boss_length_fwd_m must be >= 0")
		require(self.boss_length_aft_m >= 0.0,      "[oxidizer_tank] boss_length_aft_m must be >= 0")

@dataclass(frozen=True)
class PressurantTankConfig:
	wall              : str    # Wall layup id from the materials file
	gas               : str    # Pressurant gas id from the materials file
	pressure_bar      : float  # Fill pressure of the bottle [bar]
	safety_factor     : float  # Burst pressure over fill pressure [-]
	mass_margin       : float  # Pressurant loaded over the computed need, as a factor [-]
	boss_length_fwd_m : float  # Forward boss fitting length [m]
	boss_length_aft_m : float  # Aft boss fitting length [m]
	reg_margin_bar    : float  # Bottle pressure left over the oxidizer tank pressure at burnout [bar]
	ambient_temp_c    : float  # Bottle temperature at fill [degC]

	def __post_init__(self):
		require_positive(self, "pressure_bar")
		require(self.safety_factor >= 1.0,     "[pressurizer_tank] safety_factor must be >= 1")
		require(self.mass_margin >= 1.0,       "[pressurizer_tank] mass_margin must be >= 1")
		require(self.boss_length_fwd_m >= 0.0, "[pressurizer_tank] boss_length_fwd_m must be >= 0")
		require(self.boss_length_aft_m >= 0.0, "[pressurizer_tank] boss_length_aft_m must be >= 0")
		require(self.reg_margin_bar >= 0.0,    "[pressurizer_tank] reg_margin_bar must be >= 0")
		require(
			self.ambient_temp_c > -CONSTANTS.universal.zero_celsius,
			"[pressurizer_tank] ambient_temp_c must be above absolute zero",
		)
#endregion

#region Engine
@dataclass(frozen=True)
class InjectorConfig:
	cd : float  # Discharge coefficient of the injector orifices [-]

	def __post_init__(self):
		require(0.0 < self.cd <= 1.0, "[injector] cd must be in (0, 1]")

@dataclass(frozen=True)
class FuelConfig:
	port_diam_m             : float  # Initial diameter of the fuel grain port [m]
	reg_exponent            : float  # Exponent n of the regression law r = a (G_ox / G_ref)^n [-]
	reg_ref_ms              : float  # Regression rate a at the reference oxidizer flux [m/s]
	oxy_mass_flux_ref_kgm2s : float  # Reference oxidizer mass flux G_ref [kg/(m^2*s)]

	def __post_init__(self):
		require_positive(self, "port_diam_m", "reg_exponent", "reg_ref_ms", "oxy_mass_flux_ref_kgm2s")

@dataclass(frozen=True)
class NozzleConfig:
	nozzle_exit_diameter_m        : float  # Fixed exit diameter, sets the expansion ratio with the throat [m]
	conical_nozzle_half_angle_deg : float  # Half angle of the conical divergent section [deg]

	def __post_init__(self):
		require_positive(self, "nozzle_exit_diameter_m")
		require(
			0.0 < self.conical_nozzle_half_angle_deg < 90.0,
			"[nozzle] conical_nozzle_half_angle_deg must be in (0, 90)",
		)
#endregion

#region Models and efficiencies
@dataclass(frozen=True)
class ModelsConfig:
	atmosphere        : str  # "auto", "isacalc" or "standalone"
	chemistry         : str  # "auto", "cea" or "rocketcea"
	pressurant_thermo : str  # "auto", "coolprop" or "ideal"

	def __post_init__(self):
		choices = {
			"atmosphere"        : ("auto", "isacalc", "standalone"),
			"chemistry"         : ("auto", "cea", "rocketcea"),
			"pressurant_thermo" : ("auto", "coolprop", "ideal"),
		}
		for name, allowed in choices.items():
			value = getattr(self, name)
			require(value in allowed, f"[models] {name} must be one of {', '.join(allowed)} (got '{value}')")

@dataclass(frozen=True)
class EfficienciesConfig:
	combustion             : float  # Delivered over ideal characteristic velocity c* [-]
	trajectory             : float  # Real apogee over the 1D apogee, for 3D flight losses [-]
	propellant_utilization : float  # Burned over loaded propellant mass [-]
	regression_correction  : float  # Real over modeled fuel regression rate [-]
	nozzle_friction        : float  # Thrust left after wall friction losses [-]

	def __post_init__(self):
		for f in fields(self):
			value = getattr(self, f.name)
			require(0.0 < value <= 1.0, f"[efficiencies] {f.name} must be in (0, 1] (got {value})")
#endregion

#region Optimization
@dataclass(frozen=True)
class DesignVariable:
	start : float  # Value the optimizer starts from
	lower : float  # Lower bound
	upper : float  # Upper bound

	def __post_init__(self):
		require(
			0.0 < self.lower <= self.start <= self.upper,
			f"Design variable needs 0 < lower <= start <= upper (got {self})",
		)

@dataclass(frozen=True)
class OptimizationConfig:
	propellant_mass_kg    : DesignVariable  # Burned propellant mass [kg]
	mixture_ratio         : DesignVariable  # Oxidizer over fuel mass flow [-]
	injector_area_m2      : DesignVariable  # Total injector orifice area [m^2]
	nozzle_throat_area_m2 : DesignVariable  # Nozzle throat area [m^2]

@dataclass(frozen=True)
class ConstraintsConfig:
	max_burn_time_s                : float  # Longest allowed burn [s]
	min_injector_pressure_drop_bar : float  # Smallest allowed injector pressure drop [bar]

	def __post_init__(self):
		require_positive(self, "max_burn_time_s", "min_injector_pressure_drop_bar")

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
		require(self.low_liftoff_twr >= self.min_liftoff_twr,         "[checks] low_liftoff_twr must be >= min_liftoff_twr")
		require(self.max_isp_s > self.min_isp_s,                      "[checks] max_isp_s must exceed min_isp_s")
		require(self.max_flame_temperature_k > self.min_flame_temperature_k, "[checks] max_flame_temperature_k must exceed min_flame_temperature_k")

@dataclass(frozen=True)
class SweepConfig:
	outer_diameters_m : tuple[float, ...]  # Outer airframe diameters to re-optimize at with --sweep [m]

	def __post_init__(self):
		require(len(self.outer_diameters_m) > 0, "[sweep] outer_diameters_m cannot be empty")
#endregion

#region Master record
@dataclass(frozen=True)
class RocketConfig:
	cfg_global       : GlobalConfig          # [global]
	cfg_aero         : AerodynamicsConfig    # [aerodynamics]
	cfg_oxy_tank     : OxidizerTankConfig    # [oxidizer_tank]
	cfg_press_tank   : PressurantTankConfig  # [pressurizer_tank]
	cfg_injector     : InjectorConfig        # [injector]
	cfg_fuel         : FuelConfig            # [fuel]
	cfg_nozzle       : NozzleConfig          # [nozzle]
	cfg_models       : ModelsConfig          # [models]
	cfg_efficiencies : EfficienciesConfig    # [efficiencies]
	cfg_optim        : OptimizationConfig    # [optimization]
	cfg_constraints  : ConstraintsConfig     # [constraints]
	cfg_checks       : ChecksConfig          # [checks]
	cfg_sweep        : SweepConfig           # [sweep]

	def __post_init__(self):
		gl, ox, pr, nz = self.cfg_global, self.cfg_oxy_tank, self.cfg_press_tank, self.cfg_nozzle

		# The injector needs a pressure drop to feed the chamber
		require(
			gl.target_chamber_pressure_bar < ox.pressure_bar,
			"[global] target_chamber_pressure_bar must be below [oxidizer_tank] pressure_bar",
		)

		# The bottle has to stay above the regulated tank pressure until burnout
		require(
			pr.pressure_bar > ox.pressure_bar + pr.reg_margin_bar,
			"[pressurizer_tank] pressure_bar must exceed the [oxidizer_tank] "
			"pressure_bar plus reg_margin_bar",
		)

		# The nozzle is part of the engine, so it sits inside the airframe bore
		require(
			nz.nozzle_exit_diameter_m <= gl.inner_rocket_diameter_m,
			"[nozzle] nozzle_exit_diameter_m must fit [global] inner_rocket_diameter_m",
		)

		# The throat has to stay smaller than the exit, so the nozzle expands
		a_exit = 0.25 * pi * nz.nozzle_exit_diameter_m**2
		require(
			self.cfg_optim.nozzle_throat_area_m2.upper < a_exit,
			f"[optimization] nozzle_throat_area_m2 upper bound must be below the "
			f"nozzle exit area ({a_exit:.4e} m^2)",
		)

		# The sweep keeps the airframe wall thickness, so the bore stays open
		wall = gl.outer_rocket_diameter_m - gl.inner_rocket_diameter_m
		require(
			all(d > wall for d in self.cfg_sweep.outer_diameters_m),
			f"[sweep] outer_diameters_m must exceed the airframe wall ({wall} m)",
		)
#endregion

#region Loader
SECTIONS = {
	"cfg_global"       : ("global",           GlobalConfig),
	"cfg_aero"         : ("aerodynamics",     AerodynamicsConfig),
	"cfg_oxy_tank"     : ("oxidizer_tank",    OxidizerTankConfig),
	"cfg_press_tank"   : ("pressurizer_tank", PressurantTankConfig),
	"cfg_injector"     : ("injector",         InjectorConfig),
	"cfg_fuel"         : ("fuel",             FuelConfig),
	"cfg_nozzle"       : ("nozzle",           NozzleConfig),
	"cfg_models"       : ("models",           ModelsConfig),
	"cfg_efficiencies" : ("efficiencies",     EfficienciesConfig),
	"cfg_optim"        : ("optimization",     OptimizationConfig),
	"cfg_constraints"  : ("constraints",      ConstraintsConfig),
	"cfg_checks"       : ("checks",           ChecksConfig),
	"cfg_sweep"        : ("sweep",            SweepConfig),
}

def _load_section(name: str, cls, table: dict):
	if cls is OptimizationConfig:
		check_keys(table, name, {f.name for f in fields(cls)})
		return cls(**{
			key: build(DesignVariable, value, f"{name}.{key}")
			for key, value in table.items()
		})

	if cls in (AerodynamicsConfig, SweepConfig):
		# TOML arrays become tuples, so the frozen record is immutable
		check_keys(table, name, {f.name for f in fields(cls)})
		return cls(**{key: tuple(value) for key, value in table.items()})

	return build(cls, table, name)

def load_rocket_inputs(path: str | Path = INPUTS_DIR / "rocket_inputs.toml") -> RocketConfig:
	with open(path, "rb") as f:
		data = tomllib.load(f)

	check_keys(data, "rocket inputs file", {name for name, _ in SECTIONS.values()})

	return RocketConfig(**{
		field: _load_section(name, cls, data[name])
		for field, (name, cls) in SECTIONS.items()
	})
#endregion
