#region Imports
import openmdao.api as om

from math         import pi
from openmdao.api import Problem

from ..BEARS_Chem      import BEARS_Chem
from ..BEARS_Materials import Gas
from ..BEARS_Vessels   import LayeredWall
from ..BEARS_Atmo      import BEARS_Atm
from ..BEARS_Thermo    import create_pressurant_thermo
from ..Config          import RocketConfig, CONSTANTS, load_configs

from .group_rocket import RocketGroup
from .reporting    import write_output_table, write_graphs
from .checks       import CheckFn, DEFAULT_ROCKET_CHECKS, run_checks
#endregion

g = CONSTANTS.universal.standard_gravity # Standard gravity [m/s^2]

class RocketLaunchProblem(Problem):

	def __init__(
		self,
		atm                 : BEARS_Atm,
		chem                : BEARS_Chem,
		ox_wall_material    : LayeredWall,
		press_wall_material : LayeredWall,
		press_gas           : Gas,
		cfg_rocket          : RocketConfig | None = None,
		non_propulsion_mass : float | None = None,
		target_apogee       : float | None = None,
		press_thermo_model  = None,
		checks              : tuple[CheckFn, ...] = DEFAULT_ROCKET_CHECKS,
		**kwargs,
	):
		super().__init__(**kwargs)

		if cfg_rocket is None:
			cfg_rocket = load_configs()

		self.cfg_rocket = cfg_rocket

		if chem.p_vap_ox is None:
			raise ValueError(
				"The oxidizer needs a vapor_pressure_bar entry in the materials "
				"file to size the pressurant pad gas"
			)
		self.p_vap_ox = chem.p_vap_ox

		if press_thermo_model is None:
			press_thermo_model = create_pressurant_thermo(
				cfg_rocket.cfg_models.pressurant_thermo,
				use_coolprop_psat=cfg_rocket.cfg_models.pressurant_psat,
			)

		self.model = RocketGroup(
			atm                 = atm,
			chem                = chem,
			ox_wall_material    = ox_wall_material,
			press_wall_material = press_wall_material,
			press_gas           = press_gas,
			press_thermo_model  = press_thermo_model,
			cfg_aero            = cfg_rocket.cfg_aero,
		)

		self.driver = om.ScipyOptimizeDriver()
		self.driver.options["optimizer"] = "SLSQP"

		self.checks = checks

		# - Design variables

		# Explicit arguments override the config file values
		gl = cfg_rocket.cfg_global

		self.non_propulsion_mass = (
			non_propulsion_mass if non_propulsion_mass is not None
			else gl.non_propulsion_mass_kg
		)

		self.target_apogee = (
			target_apogee if target_apogee is not None
			else gl.target_altitude_m
		)

		eff_apogee = self.target_apogee / cfg_rocket.cfg_efficiencies.trajectory

		target_thrust = gl.target_thrust_N
		target_pc     = gl.target_chamber_pressure_bar

		self.model.add_design_var(
			"OptimizationVars.o_propellant_mass",
			lower = 1.0,
			upper = 10.0,
			ref   = 5.0,
		)

		self.model.add_design_var(
			"OptimizationVars.o_mixture_ratio",
			lower = 4.0,
			upper = 10.0,
			ref   = 6.0,
		)

		self.model.add_design_var(
			"OptimizationVars.o_injector_area",
			lower = 0.5e-5,
			upper = 3.0e-4,
			ref   = 1.5e-5,
		)

		# The nozzle exit is fixed, so the throat area sets the expansion
		# ratio, eps = A_exit / A_throat. The throat is kept between 1 cm^2 and
		# 99 % of the exit area, so that eps stays above 1
		a_exit = 0.25 * pi * cfg_rocket.cfg_nozzle.nozzle_exit_diameter_m**2
		a_min  = 1.0e-4
		a_max  = 0.99 * a_exit
		if a_min >= a_max:
			raise ValueError(
				f"The nozzle exit area ({a_exit * 1e4:.3f} cm^2) is too small "
				"for the smallest allowed throat (1 cm^2)"
			)

		self.model.add_design_var(
			"OptimizationVars.o_nozzle_throat_area",
			lower = a_min,
			upper = a_max,
			ref   = 5.0e-4,
		)

		# - Constraints
		self.model.add_constraint(
			"apogee",
			lower = eff_apogee,
			ref   = eff_apogee,
		)

		# The thrust and apogee targets fix the burn time, so it has no lower
		# bound, only a sanity cap
		self.model.add_constraint(
			"burn_time",
			upper = 15.0,
			ref   = 6.0,
		)

		# The engine is sized to deliver the target thrust at the target
		# chamber pressure
		self.model.add_constraint(
			"Propulsion.prop_thrust",
			equals = target_thrust,
			ref    = target_thrust,
			units  = "N",
		)

		self.model.add_constraint(
			"Propulsion.prop_chamber_pressure",
			equals = target_pc,
			ref    = target_pc,
			units  = "bar",
		)

		# The fuel grain has to fit inside the airframe bore
		self.model.add_constraint(
			"EngineFit.grain_margin",
			lower = 0.0,
			ref   = 0.01,
			units = "m",
		)

		# Injector pressure drop safety margin
		self.model.add_constraint(
			"Propulsion.injector_delta_p",
			lower = 20.0,
			ref   = 20.0,
			units = "bar",
		)

		# - Objective
		self.model.add_objective(
			"OptimizationVars.o_propellant_mass",
			ref = 10.0,
		)

	def setup(self, **kwargs):
		super().setup(**kwargs)

		cfg = self.cfg_rocket
		gl  = cfg.cfg_global
		ox  = cfg.cfg_oxy_tank
		pr  = cfg.cfg_press_tank
		inj = cfg.cfg_injector
		fu  = cfg.cfg_fuel
		nz  = cfg.cfg_nozzle
		ef  = cfg.cfg_efficiencies
		so  = cfg.cfg_optim

		# Vehicle parameters
		self.set_val("DesignVars.g_non_propulsion_mass",     self.non_propulsion_mass,       units="kg")
		self.set_val("DesignVars.g_target_altitude",         self.target_apogee,             units="m")
		self.set_val("DesignVars.g_target_thrust",           gl.target_thrust_N,             units="N")
		self.set_val("DesignVars.g_target_chamber_pressure", gl.target_chamber_pressure_bar, units="bar")
		self.set_val("DesignVars.g_inner_diameter",          gl.inner_rocket_diameter_m,     units="m")
		self.set_val("DesignVars.g_outer_diameter",          gl.outer_rocket_diameter_m,     units="m")

		# The non-propulsion mass is given for the configured airframe
		self.set_val("Mass.ref_diameter", gl.outer_rocket_diameter_m, units="m")

		# Oxidizer tank
		self.set_val("DesignVars.tank_pressure",        ox.pressure_bar,      units="bar")
		self.set_val("DesignVars.tank_safety_factor",   ox.safety_factor)
		self.set_val("DesignVars.tank_ullage_fraction", ox.ullage_fraction)
		self.set_val("DesignVars.tank_boss_opening",    ox.boss_opening_m,    units="m")
		self.set_val("DesignVars.tank_boss_len_fwd",    ox.boss_length_fwd_m, units="m")
		self.set_val("DesignVars.tank_boss_len_aft",    ox.boss_length_aft_m, units="m")
		self.set_val("DesignVars.tank_vapor_pressure",  self.p_vap_ox,         units="Pa")

		# Pressurant tank
		self.set_val("DesignVars.press_pressure",       pr.pressure_bar,      units="bar")
		self.set_val("DesignVars.press_safety_factor",  pr.safety_factor)
		self.set_val("DesignVars.press_boss_opening",   pr.boss_opening_m,    units="m")
		self.set_val("DesignVars.press_boss_len_fwd",   pr.boss_length_fwd_m, units="m")
		self.set_val("DesignVars.press_boss_len_aft",   pr.boss_length_aft_m, units="m")
		self.set_val("DesignVars.press_reg_margin",     pr.reg_margin_bar,    units="bar")
		self.set_val("DesignVars.press_ambient_temp",   pr.ambient_temp_c,    units="degC")

		# Engine
		self.set_val("DesignVars.injector_cd",            inj.cd)
		self.set_val("DesignVars.fuel_port_diam",         fu.port_diam_m,             units="m")
		self.set_val("DesignVars.fuel_reg_exponent",      fu.reg_exponent)
		self.set_val("DesignVars.fuel_reg_ref",           fu.reg_ref_ms,              units="m/s")
		self.set_val("DesignVars.fuel_oxy_mass_flux_ref", fu.oxy_mass_flux_ref_kgm2s, units="kg/(m**2*s)")
		self.set_val("DesignVars.nozzle_exit_diam",       nz.nozzle_exit_diameter_m,  units="m")
		self.set_val("DesignVars.conical_nozzle_half_angle", nz.conical_nozzle_half_angle_deg, units="deg")

		self.set_val("EfficiencyVars.eta_combustion",         ef.combustion)
		self.set_val("EfficiencyVars.eta_trajectory",         ef.trajectory)
		self.set_val("EfficiencyVars.eta_propellant",         ef.propellant_utilization)
		self.set_val("EfficiencyVars.eta_regression",         ef.regression_correction)
		self.set_val("EfficiencyVars.eta_nozzle_friction",    ef.nozzle_friction)

		# Starting point for optimization
		self.set_val("OptimizationVars.o_propellant_mass",    so.propellant_mass_kg)
		self.set_val("OptimizationVars.o_mixture_ratio",      so.mixture_ratio)
		self.set_val("OptimizationVars.o_injector_area",      so.injector_area_m2)
		self.set_val("OptimizationVars.o_nozzle_throat_area", so.nozzle_throat_area_m2)

		return self

	def run(self):
		self.run_driver()
		return self

	#region Verification
	def verify(self, raise_on_error : bool = True):
		"""Validate post-run physical quantities and optimization results"""
		return run_checks(self, self.checks, raise_on_error=raise_on_error)
	#endregion

	#region Outputs
	def print_summary(self):

		FMT = "8.3f"

		self.verify()

		m_prop = self.get_val("OptimizationVars.o_propellant_mass",    units="kg")[0]
		m_ld   = self.get_val("Mass.prop_loaded_mass",                 units="kg")[0]
		a_inj  = self.get_val("OptimizationVars.o_injector_area",      units="mm**2")[0]
		a_thr  = self.get_val("OptimizationVars.o_nozzle_throat_area", units="cm**2")[0]
		d_ex   = self.get_val("DesignVars.nozzle_exit_diam",           units="mm")[0]
		eps    = self.get_val("Propulsion.nozzle_expansion_ratio")[0]
		m_ex   = self.get_val("Propulsion.nozzle_exit_mach")[0]
		mr     = self.get_val("OptimizationVars.o_mixture_ratio")[0]
		ap     = self.get_val("apogee",                                units="m")[0]
		t_burn = self.get_val("burn_time",                             units="s")[0]
		thr    = self.get_val("Propulsion.prop_thrust",                units="N")[0]
		isp    = self.get_val("Propulsion.prop_isp",                   units="s")[0]
		pch    = self.get_val("Propulsion.prop_chamber_pressure",      units="bar")[0]
		tch    = self.get_val("Propulsion.prop_chamber_temp",          units="K")[0]
		dp     = self.get_val("Propulsion.injector_delta_p",           units="bar")[0]
		mdry   = self.get_val("Mass.dry_mass",                         units="kg")[0]
		mpr    = self.get_val("Mass.pressurant_mass",                  units="kg")[0]
		mi     = self.get_val("Mass.initial_mass",                     units="kg")[0]
		twr    = thr / (mi * g)

		print("Optimized rocket parameters:")
		print("")
		print(f"Burned (optimized) m_prop:\t{m_prop:{FMT}} kg")
		print(f"Loaded m_prop:            \t{m_ld:{FMT}} kg")
		print(f"Optimized A_inj:          \t{a_inj:{FMT}} mm²")
		print(f"Optimized A_throat:       \t{a_thr:{FMT}} cm²")
		print(f"Optimized MR:             \t{mr:{FMT}}")
		print(f"Nozzle exit diameter:     \t{d_ex:{FMT}} mm")
		print(f"Expansion ratio:          \t{eps:{FMT}}")
		print("")
		print(f"Apogee:                   \t{ap:{FMT}} m")
		print(f"Burn time:                \t{t_burn:{FMT}} s")
		print(f"Liftoff thrust:           \t{thr:{FMT}} N")
		print(f"Liftoff Isp:              \t{isp:{FMT}} s")
		print(f"Chamber pressure:         \t{pch:{FMT}} bar")
		print(f"Chamber flame temp:       \t{tch:{FMT}} K")
		print(f"Injector ΔP:              \t{dp:{FMT}} bar")
		print(f"Nozzle exit Mach:         \t{m_ex:{FMT}}")
		print("")
		print(f"Dry mass:                 \t{mdry:{FMT}} kg")
		print(f"Pressurant mass:          \t{mpr:{FMT}} kg")
		print(f"Total mass at liftoff:    \t{mi:{FMT}} kg")
		print(f"TWR at launch:            \t{twr:{FMT}}")

	def print_parameters(self, path: str = "outputs/rocket.txt"):
		"""Dump all computed variables to an output file"""
		write_output_table(self.model, path)

	def print_graphs(self, out_dir: str = "figures", prefix: str = "rocket"):
		"""Draw all the connectivity graphs, provided Graphviz is installed"""
		write_graphs(self.model, out_dir, prefix)

	def report(
		self,
		out_txt : str  = "outputs/rocket.txt",
		graphs  : bool = True,
	):
		"""Print results and generate output files"""

		self.print_summary()
		self.print_parameters(out_txt)
		if graphs:
			self.print_graphs()
	#endregion
