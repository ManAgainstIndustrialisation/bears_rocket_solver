#region Imports
from dataclasses import dataclass, field

from .constants import CONSTANTS
#endregion

#region Design
@dataclass(frozen=True)
class GlobalConfig:
	non_propulsion_mass_kg      : float # Everything but the propulsion system [kg]
	target_altitude_m           : float # [m]
	target_thrust_N             : float # [N]
	target_chamber_pressure_bar : float # [bar]
	inner_rocket_diameter_m     : float # Airframe bore, holds the tanks [m]
	outer_rocket_diameter_m     : float # Airframe skin, sets the drag area [m]
	clearance_m                 : float # [m]

@dataclass(frozen=True)
class AerodynamicsConfig:
	drag_mach               : tuple[float, ...] # Mach number breakpoints, increasing
	drag_cd                 : tuple[float, ...] # Drag coefficient at each breakpoint

@dataclass(frozen=True)
class TankConfig:
	pressure_bar            : float # [bar]
	diam_m                  : float # [m]
	safety_factor           : float
	ullage_fraction         : float = 0.0
	boss_opening_m          : float = 0.02  # [m]
	boss_length_fwd_m       : float = 0.015 # [m]
	boss_length_aft_m       : float = 0.015 # [m]
	reg_margin_bar          : float = 20.0  # [bar]
	ambient_temp_c          : float = 30.0  # [deg C]

@dataclass(frozen=True)
class InjectorConfig:
	cd                      : float

@dataclass(frozen=True)
class FuelConfig:
	port_diam_m             : float # [m]
	reg_exponent            : float
	reg_ref_ms              : float # [m/s]
	oxy_mass_flux_ref_kgm2s : float # [kg/(m^2*s)]

@dataclass(frozen=True)
class IgniterConfig:
	burn_time_s             : float = 1.0    # [s]
	burn_rate_ms            : float = 0.0015 # [m/s]
	flame_spread_ms         : float = 0.15   # [m/s]
	max_spread_delay_s      : float = 0.10   # [s]
	thermite_density_kgm3   : float = 3800.0 # [kg/m^3]

@dataclass(frozen=True)
class NozzleConfig:
	nozzle_exit_diameter_m        : float # Fixed exit diameter [m]
	conical_nozzle_half_angle_deg : float # Divergent cone half angle [deg]

@dataclass(frozen=True)
class ModelsConfig:
	atmosphere              : str  = "auto"
	chemistry               : str  = "auto"
	pressurant_thermo       : str  = "auto"
	pressurant_psat         : bool = False

@dataclass(frozen=True)
class OptimizationSeedConfig:
	propellant_mass_kg      : float # [kg]
	mixture_ratio           : float
	injector_area_m2        : float # [m^2]
	nozzle_throat_area_m2   : float # [m^2]

@dataclass(frozen=True)
class EfficienciesConfig:
	combustion              : float = 0.88
	trajectory              : float = 0.92
	propellant_utilization  : float = 0.92
	regression_correction   : float = 0.60
	nozzle_friction         : float = 0.95
#endregion

#region Chemistry
@dataclass(frozen=True)
class SpeciesConfig:
	name                    : str
	formula_parts           : tuple[dict[str, float], ...] = ()
	mass_fraction           : float = 100.0
	temperature_k           : float = CONSTANTS.reference.temperature
	enthalpy                : float | None = None
	enthalpy_units          : str   | None = None
	density                 : float | None = None
	density_units           : str   | None = None
	vapor_pressure_bar      : float | None = None # Saturation pressure [bar]
	role                    : str   | None = None

@dataclass(frozen=True)
class BipropellantConfig:
	fuels                   : tuple[SpeciesConfig, ...]
	oxidizers               : tuple[SpeciesConfig, ...]
#endregion

#region Materials and Fluids
@dataclass(frozen=True)
class MaterialConfig:
	id                      : str
	name                    : str
	density                 : float
	yield_strength          : float
	ultimate_strength       : float
	elastic_modulus         : float

@dataclass(frozen=True)
class GasConfig:
	id                      : str
	name                    : str
	molar_mass              : float # [kg/kmol]
	gamma                   : float
	coolprop_name           : str   | None = None
	z_factor                : float        = 1.0
	t_crit_k                : float | None = None
	p_crit_pa               : float | None = None
	acentric                : float        = 0.0

	@property
	def r_specific(self) -> float:
		"""R / M [J/(kg*K)], with the molar mass converted to kg/mol"""
		return CONSTANTS.universal.molar_gas_constant / (self.molar_mass * 1e-3)

@dataclass(frozen=True)
class LayerConfig:
	material_id       : str
	thickness_m       : float | None = None # None for pressure-sized
	is_load_bearing   : bool         = True # False for thermal insulation
	helical_angle_deg : float | None = None # None for isotropic or dynamic boss
	efficiency        : float        = 0.85 # Fiber translation efficiency
	fiber_volume_frac : float        = 0.72 # Fiber volume fraction

@dataclass(frozen=True)
class WallConfig:
	id                : str
	layers            : tuple[LayerConfig, ...]

@dataclass(frozen=True)
class MaterialsConfig:
	materials         : tuple[MaterialConfig, ...]
	walls             : tuple[WallConfig, ...]

@dataclass(frozen=True)
class FluidsConfig:
	gases             : tuple[GasConfig, ...]
#endregion

#region Master specification
@dataclass(frozen=True)
class RocketConfig:
	cfg_global        : GlobalConfig
	cfg_aero          : AerodynamicsConfig
	cfg_oxy_tank      : TankConfig
	cfg_press_tank    : TankConfig
	cfg_injector      : InjectorConfig
	cfg_fuel          : FuelConfig
	cfg_igniter       : IgniterConfig
	cfg_nozzle        : NozzleConfig
	cfg_optim         : OptimizationSeedConfig
	cfg_models        : ModelsConfig = (
		field(default_factory=ModelsConfig)
	)
	cfg_efficiencies  : EfficienciesConfig = (
		field(default_factory=EfficienciesConfig)
	)
#endregion
