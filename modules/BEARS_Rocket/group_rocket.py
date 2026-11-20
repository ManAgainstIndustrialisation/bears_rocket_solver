#region Imports
from openmdao.api import Group, IndepVarComp, ExecComp

from ..BEARS_Chem      import BEARS_Chem
from ..BEARS_Atmo      import BEARS_Atm
from ..BEARS_Materials import Gas
from ..BEARS_Vessels   import LayeredWall
from ..Config          import AerodynamicsConfig

from .group_prop import PropulsionGroup
from .comp_mass  import MassComponent
from .comp_traj  import TrajectoryComponent
#endregion

class RocketGroup(Group):

	def initialize(self):
		self.options.declare("chem", types=BEARS_Chem)
		self.options.declare("atm",  types=BEARS_Atm)

		self.options.declare("ox_wall_material",    types=LayeredWall)
		self.options.declare("press_wall_material", types=LayeredWall)
		self.options.declare("press_gas",           types=Gas)
		self.options.declare("press_thermo_model",  default=None)
		self.options.declare("cfg_aero",            types=AerodynamicsConfig)

	def setup(self):
		chem         = self.options["chem"]
		atm          = self.options["atm"]
		ox_wall      = self.options["ox_wall_material"]
		press_wall   = self.options["press_wall_material"]
		press_gas    = self.options["press_gas"]
		press_thermo = self.options["press_thermo_model"]

		#region Independent variable components
		# DesignVars:
		# catch-all for free design parameters
		ivc = self.add_subsystem("DesignVars", IndepVarComp())

		# - Global/master inputs
		ivc.add_output("g_non_propulsion_mass",     val=8.0,    units="kg")
		ivc.add_output("g_target_altitude",         val=3000.0, units="m")
		ivc.add_output("g_target_thrust",           val=3000.0, units="N")
		ivc.add_output("g_target_chamber_pressure", val=30.0,   units="bar")

		# Airframe diameters: the tanks are structural and form the skin, so
		# they take the outer diameter, which also sets the drag. The engine
		# is not structural and sits inside the bore, the inner diameter
		ivc.add_output("g_inner_diameter",       val=0.12,   units="m")
		ivc.add_output("g_outer_diameter",       val=0.125,  units="m")

		# - Oxidizer tank
		# NOTE: the tank component expects pressure in SI Pa units,
		#       here we specify the pressure in units of bar used by the team
		#       and let MDAO convert automatically on component interface
		ivc.add_output("tank_pressure",          val=70,     units="bar")
		ivc.add_output("tank_safety_factor",     val=2.0)
		ivc.add_output("tank_ullage_fraction",   val=0.1)
		ivc.add_output("tank_boss_opening",      val=0.02,   units="m")
		ivc.add_output("tank_boss_len_fwd",      val=0.015,  units="m")
		ivc.add_output("tank_boss_len_aft",      val=0.019,  units="m")
		ivc.add_output("tank_vapor_pressure",    val=60.0,   units="bar")

		# - Pressurant tank
		ivc.add_output("press_pressure",         val=200,    units="bar")
		ivc.add_output("press_safety_factor",    val=2.0)
		ivc.add_output("press_boss_opening",     val=0.02,   units="m")
		ivc.add_output("press_boss_len_fwd",     val=0.015,  units="m")
		ivc.add_output("press_boss_len_aft",     val=0.015,  units="m")
		ivc.add_output("press_reg_margin",       val=20,     units="bar")
		ivc.add_output("press_ambient_temp",     val=30.0,   units="degC")

		# - Injector
		ivc.add_output("injector_cd",            val=0.7)

		# - Fuel
		ivc.add_output("fuel_port_diam",         val=0.05,   units="m")
		ivc.add_output("fuel_reg_exponent",      val=0.5)
		ivc.add_output("fuel_reg_ref",           val=1.0e-4, units="m/s")
		ivc.add_output("fuel_oxy_mass_flux_ref", val=1.0,    units="kg/(m**2*s)")

		# - Nozzle
		ivc.add_output("nozzle_exit_diam",       val=0.065,  units="m")
		ivc.add_output("conical_nozzle_half_angle", val=15.0, units="deg")

		# Efficiencies:
		evc = self.add_subsystem("EfficiencyVars", IndepVarComp())
		evc.add_output("eta_combustion",         val=0.88)
		evc.add_output("eta_trajectory",         val=0.92)
		evc.add_output("eta_propellant",         val=0.92)
		evc.add_output("eta_regression",         val=0.60)
		evc.add_output("eta_nozzle_friction",    val=0.95)

		# OptimizationVars:
		# specific parameters that we wish to optimize against
		ovc = self.add_subsystem("OptimizationVars", IndepVarComp())
		ovc.add_output("o_propellant_mass",    val=10.0,   units="kg")
		ovc.add_output("o_mixture_ratio",      val=6.0)
		ovc.add_output("o_injector_area",      val=1.5e-5, units="m**2")
		ovc.add_output("o_nozzle_throat_area", val=7.0e-4, units="m**2")
		#endregion

		#region Subsystems
		self.add_subsystem(
			"Propulsion",
			PropulsionGroup(
				chem                = chem,
				ox_wall_material    = ox_wall,
				press_wall_material = press_wall,
				press_gas           = press_gas,
				press_thermo_model  = press_thermo,
			),
		)

		self.add_subsystem("Mass", MassComponent())

		# Radial room left between the fuel grain and the airframe bore
		self.add_subsystem(
			"EngineFit",
			ExecComp(
				"grain_margin = d_inner - d_grain",
				grain_margin = {"val": 0.05, "units": "m"},
				d_inner      = {"val": 0.12, "units": "m"},
				d_grain      = {"val": 0.07, "units": "m"},
			),
		)

		self.add_subsystem(
			"Trajectory",
			TrajectoryComponent(atm=atm, aero=self.options["cfg_aero"]),
			promotes_outputs=["burn_time", "apogee"],
		)
		#endregion

		#region Connections
		# - Oxidizer tank
		self.connect("DesignVars.tank_pressure",           "Propulsion.tank_pressure")
		self.connect("DesignVars.g_outer_diameter",        "Propulsion.tank_diam")
		self.connect("DesignVars.tank_safety_factor",      "Propulsion.tank_safety_factor")
		self.connect("DesignVars.tank_ullage_fraction",    "Propulsion.tank_ullage_frac")
		self.connect("DesignVars.tank_boss_opening",       "Propulsion.tank_boss_opening")
		self.connect("DesignVars.tank_boss_len_fwd",       "Propulsion.tank_boss_len_fwd")
		self.connect("DesignVars.tank_boss_len_aft",       "Propulsion.tank_boss_len_aft")
		self.connect("DesignVars.tank_vapor_pressure",     "Propulsion.tank_vapor_pressure")

		# - Pressurant tank
		self.connect("DesignVars.press_pressure",          "Propulsion.press_pressure")
		self.connect("DesignVars.g_outer_diameter",        "Propulsion.press_diam")
		self.connect("DesignVars.press_safety_factor",     "Propulsion.press_safety_factor")
		self.connect("DesignVars.press_boss_opening",      "Propulsion.press_boss_opening")
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
		self.connect("DesignVars.nozzle_exit_diam",        "Propulsion.nozzle_exit_diam")
		self.connect("DesignVars.conical_nozzle_half_angle", "Propulsion.conical_nozzle_half_angle")

		# - Engine fit
		self.connect("DesignVars.g_inner_diameter",        "EngineFit.d_inner")
		self.connect("Propulsion.fuel_grain_diam",         "EngineFit.d_grain")

		# - Mass
		self.connect("DesignVars.g_non_propulsion_mass",   "Mass.non_propulsion_mass")
		self.connect("DesignVars.g_outer_diameter",        "Mass.diameter")
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
