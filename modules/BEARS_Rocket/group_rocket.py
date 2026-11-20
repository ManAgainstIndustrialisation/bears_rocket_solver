#region Imports
from openmdao.api import Group, IndepVarComp, ExecComp

from ..BEARS_Atmo   import BEARS_Atm
from ..BEARS_Chem   import BEARS_Chem
from ..BEARS_Thermo import PressurantThermoModel
from ..Config       import RocketConfig, Gas, Wall

from .group_prop import PropulsionGroup
from .comp_mass  import MassComponent
from .comp_traj  import TrajectoryComponent
#endregion

class RocketGroup(Group):
	"""
	The whole rocket: propulsion, mass budget and trajectory

	The independent variables are taken from the rocket inputs, with the units
	of the input file. OpenMDAO converts them to SI at each connection
	"""

	def initialize(self):
		self.options.declare("cfg",          types=RocketConfig)           # Rocket design inputs
		self.options.declare("chem",         types=BEARS_Chem)             # Chemistry of the propellant combination
		self.options.declare("atm",          types=BEARS_Atm)              # Atmosphere model
		self.options.declare("ox_wall",      types=Wall)                   # Oxidizer tank wall layup
		self.options.declare("press_wall",   types=Wall)                   # Pressurant bottle wall layup
		self.options.declare("press_gas",    types=Gas)                    # Pressurant gas
		self.options.declare("press_thermo", types=PressurantThermoModel)  # Pressurant blowdown model

	def setup(self):
		cfg  = self.options["cfg"]
		chem = self.options["chem"]
		gl   = cfg.cfg_global
		ox   = cfg.cfg_oxy_tank
		pr   = cfg.cfg_press_tank
		fu   = cfg.cfg_fuel
		nz   = cfg.cfg_nozzle
		ef   = cfg.cfg_efficiencies
		op   = cfg.cfg_optim

		#region Independent variables
		# DesignVars: fixed design parameters
		ivc = self.add_subsystem("DesignVars", IndepVarComp())

		# - Vehicle
		ivc.add_output("g_non_propulsion_mass",     val=gl.non_propulsion_mass_kg,      units="kg")   # Everything but the propulsion system
		ivc.add_output("g_engine_dry_mass",         val=gl.engine_dry_mass_kg,          units="kg")   # Engine hardware without propellant
		ivc.add_output("g_target_altitude",         val=gl.target_altitude_m,           units="m")    # Apogee target
		ivc.add_output("g_target_thrust",           val=gl.target_thrust_N,             units="N")    # Thrust target
		ivc.add_output("g_target_chamber_pressure", val=gl.target_chamber_pressure_bar, units="bar")  # Chamber pressure target

		# The tanks are structural and form the skin, so they take the outer
		# diameter, which also sets the drag. The engine is not structural and
		# sits inside the bore, the inner diameter
		ivc.add_output("g_inner_diameter",          val=gl.inner_rocket_diameter_m,     units="m")    # Airframe bore
		ivc.add_output("g_outer_diameter",          val=gl.outer_rocket_diameter_m,     units="m")    # Airframe skin
		ivc.add_output("g_ref_outer_diameter",      val=gl.outer_rocket_diameter_m,     units="m")    # Outer diameter the non-propulsion mass is given at

		# - Oxidizer tank
		ivc.add_output("tank_pressure",        val=ox.pressure_bar,      units="bar")  # Maximum operating pressure
		ivc.add_output("tank_safety_factor",   val=ox.safety_factor)                   # Burst over operating pressure [-]
		ivc.add_output("tank_ullage_fraction", val=ox.ullage_fraction)                 # Gas-filled share at loading [-]
		ivc.add_output("tank_boss_len_fwd",    val=ox.boss_length_fwd_m, units="m")    # Forward boss length
		ivc.add_output("tank_boss_len_aft",    val=ox.boss_length_aft_m, units="m")    # Aft boss length
		ivc.add_output("tank_vapor_pressure",  val=chem.p_vap_ox,        units="Pa")   # Oxidizer saturation pressure

		# - Pressurant bottle
		ivc.add_output("press_pressure",       val=pr.pressure_bar,      units="bar")   # Fill pressure
		ivc.add_output("press_safety_factor",  val=pr.safety_factor)                    # Burst over fill pressure [-]
		ivc.add_output("press_boss_len_fwd",   val=pr.boss_length_fwd_m, units="m")     # Forward boss length
		ivc.add_output("press_boss_len_aft",   val=pr.boss_length_aft_m, units="m")     # Aft boss length
		ivc.add_output("press_reg_margin",     val=pr.reg_margin_bar,    units="bar")   # Bottle pressure left over the tank pressure at burnout
		ivc.add_output("press_ambient_temp",   val=pr.ambient_temp_c,    units="degC")  # Bottle temperature at fill

		# - Engine
		ivc.add_output("injector_cd",               val=cfg.cfg_injector.cd)                             # Injector discharge coefficient [-]
		ivc.add_output("fuel_port_diam",            val=fu.port_diam_m,             units="m")           # Initial port diameter
		ivc.add_output("fuel_reg_exponent",         val=fu.reg_exponent)                                 # Regression law exponent [-]
		ivc.add_output("fuel_reg_ref",              val=fu.reg_ref_ms,              units="m/s")         # Regression rate at the reference flux
		ivc.add_output("fuel_oxy_mass_flux_ref",    val=fu.oxy_mass_flux_ref_kgm2s, units="kg/(m**2*s)") # Reference oxidizer mass flux
		ivc.add_output("nozzle_exit_diam",          val=nz.nozzle_exit_diameter_m,  units="m")           # Nozzle exit diameter
		ivc.add_output("conical_nozzle_half_angle", val=nz.conical_nozzle_half_angle_deg, units="deg")   # Divergent cone half angle

		# EfficiencyVars: efficiencies on the ideal models [-]
		evc = self.add_subsystem("EfficiencyVars", IndepVarComp())
		evc.add_output("eta_combustion",      val=ef.combustion)              # Delivered over ideal c*
		evc.add_output("eta_trajectory",      val=ef.trajectory)              # Real over 1D apogee
		evc.add_output("eta_propellant",      val=ef.propellant_utilization)  # Burned over loaded propellant
		evc.add_output("eta_regression",      val=ef.regression_correction)   # Real over modeled regression rate
		evc.add_output("eta_nozzle_friction", val=ef.nozzle_friction)         # Thrust left after wall friction

		# OptimizationVars: the design variables, at the optimizer start values
		ovc = self.add_subsystem("OptimizationVars", IndepVarComp())
		ovc.add_output("o_propellant_mass",    val=op.propellant_mass_kg.start,    units="kg")    # Burned propellant mass
		ovc.add_output("o_mixture_ratio",      val=op.mixture_ratio.start)                        # Oxidizer over fuel mass flow [-]
		ovc.add_output("o_injector_area",      val=op.injector_area_m2.start,      units="m**2")  # Total injector orifice area
		ovc.add_output("o_nozzle_throat_area", val=op.nozzle_throat_area_m2.start, units="m**2")  # Nozzle throat area
		#endregion

		#region Subsystems
		self.add_subsystem(
			"Propulsion",
			PropulsionGroup(
				chem         = chem,
				ox_wall      = self.options["ox_wall"],
				press_wall   = self.options["press_wall"],
				press_gas    = self.options["press_gas"],
				press_thermo = self.options["press_thermo"],
			),
		)

		self.add_subsystem("Mass", MassComponent())

		# Radial room between the fuel grain and the airframe bore
		self.add_subsystem(
			"EngineFit",
			ExecComp(
				"grain_margin = d_inner - d_grain",
				grain_margin = {"units": "m"},  # Bore diameter left over the grain
				d_inner      = {"units": "m"},  # Airframe bore
				d_grain      = {"units": "m"},  # Fuel grain outer diameter
			),
		)

		self.add_subsystem(
			"Trajectory",
			TrajectoryComponent(atm=self.options["atm"], aero=cfg.cfg_aero),
			promotes_outputs=["burn_time", "apogee"],
		)
		#endregion

		#region Connections
		# - Oxidizer tank
		self.connect("DesignVars.tank_pressure",           "Propulsion.tank_pressure")
		self.connect("DesignVars.g_outer_diameter",        "Propulsion.tank_diam")
		self.connect("DesignVars.tank_safety_factor",      "Propulsion.tank_safety_factor")
		self.connect("DesignVars.tank_ullage_fraction",    "Propulsion.tank_ullage_frac")
		self.connect("DesignVars.tank_boss_len_fwd",       "Propulsion.tank_boss_len_fwd")
		self.connect("DesignVars.tank_boss_len_aft",       "Propulsion.tank_boss_len_aft")
		self.connect("DesignVars.tank_vapor_pressure",     "Propulsion.tank_vapor_pressure")

		# - Pressurant bottle
		self.connect("DesignVars.press_pressure",          "Propulsion.press_pressure")
		self.connect("DesignVars.g_outer_diameter",        "Propulsion.press_diam")
		self.connect("DesignVars.press_safety_factor",     "Propulsion.press_safety_factor")
		self.connect("DesignVars.press_boss_len_fwd",      "Propulsion.press_boss_len_fwd")
		self.connect("DesignVars.press_boss_len_aft",      "Propulsion.press_boss_len_aft")
		self.connect("DesignVars.press_reg_margin",        "Propulsion.press_reg_margin")
		self.connect("DesignVars.press_ambient_temp",      "Propulsion.press_ambient_temp")

		# - Fuel
		self.connect("DesignVars.fuel_port_diam",          "Propulsion.fuel_port_diam")
		self.connect("DesignVars.fuel_reg_exponent",       "Propulsion.fuel_reg_exponent")
		self.connect("DesignVars.fuel_reg_ref",            "Propulsion.fuel_reg_ref")
		self.connect("DesignVars.fuel_oxy_mass_flux_ref",  "Propulsion.fuel_oxy_mass_flux_ref")

		# - Injector
		self.connect("DesignVars.injector_cd",             "Propulsion.injector_cd")

		# - Nozzle
		self.connect("DesignVars.nozzle_exit_diam",          "Propulsion.nozzle_exit_diam")
		self.connect("DesignVars.conical_nozzle_half_angle", "Propulsion.conical_nozzle_half_angle")

		# - Engine fit
		self.connect("DesignVars.g_inner_diameter",        "EngineFit.d_inner")
		self.connect("Propulsion.fuel_grain_diam",         "EngineFit.d_grain")

		# - Mass
		self.connect("DesignVars.g_non_propulsion_mass",   "Mass.non_propulsion_mass")
		self.connect("DesignVars.g_engine_dry_mass",       "Mass.engine_dry_mass")
		self.connect("DesignVars.g_outer_diameter",        "Mass.diameter")
		self.connect("DesignVars.g_ref_outer_diameter",    "Mass.ref_diameter")
		self.connect("Propulsion.tank_dry_mass",           "Mass.ox_tank_mass")
		self.connect("Propulsion.press_dry_mass",          "Mass.press_tank_mass")
		self.connect("Propulsion.press_press_mass",        "Mass.pressurant_mass")

		# - Trajectory
		self.connect("DesignVars.g_outer_diameter",        "Trajectory.diameter")
		self.connect("Propulsion.prop_isp",                "Trajectory.isp")
		self.connect("Propulsion.prop_thrust",             "Trajectory.thrust")
		self.connect("Mass.initial_mass",                  "Trajectory.initial_mass")

		# - Efficiencies
		self.connect("EfficiencyVars.eta_regression",      "Propulsion.fuel_eta_reg")
		self.connect("EfficiencyVars.eta_combustion",      "Propulsion.chem_eta_cstar")
		self.connect("EfficiencyVars.eta_propellant",      "Mass.eta_prop")
		self.connect("EfficiencyVars.eta_nozzle_friction", "Propulsion.nozzle_eta_friction")

		# - Optimization
		self.connect("OptimizationVars.o_propellant_mass",    "Trajectory.propellant_mass")
		self.connect("OptimizationVars.o_mixture_ratio",      "Propulsion.prop_mixture_ratio")
		self.connect("OptimizationVars.o_propellant_mass",    "Propulsion.prop_prop_mass_init")
		self.connect("OptimizationVars.o_propellant_mass",    "Mass.propellant_mass")
		self.connect("OptimizationVars.o_injector_area",      "Propulsion.injector_area")
		self.connect("OptimizationVars.o_nozzle_throat_area", "Propulsion.nozzle_throat_area")
		#endregion
