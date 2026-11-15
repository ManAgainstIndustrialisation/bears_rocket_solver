#region Imports
import os
import openmdao.api as om

from scipy.constants import g
from openmdao.api    import Problem
from openmdao.visualization.graph_viewer import GraphViewer

from ..BEARS_Chem   import BEARS_Chem
from ..BEARS_Atmo   import BEARS_Atm
from ..BEARS_Thermo import create_pressurant_thermo
from ..Config     import (
	OptimizationSeedConfig,
	EfficienciesConfig,
	RocketConfig,
	load_configs,
)

from .group_rocket import RocketGroup
from .graph_style  import has_graphviz, style_graph

from .checks  import CheckFn, DEFAULT_ROCKET_CHECKS, run_checks
#endregion

class RocketLaunchProblem(Problem):

	def __init__(
		self,
		atm                 : BEARS_Atm,
		chem                : BEARS_Chem,
		cfg_rocket          : RocketConfig | None = None,
		payload_mass        : float | None = None,
		nonprop_mass        : float | None = None,
		target_apogee       : float | None = None,
		ox_wall_material    = None,
		press_wall_material = None,
		press_gas           = None,
		press_thermo_model  = None,
		checks              : tuple[CheckFn, ...] = DEFAULT_ROCKET_CHECKS,
		**kwargs,
	):
		super().__init__(**kwargs)

		if cfg_rocket is None:
			cfg_rocket = load_configs()

		self.cfg_rocket = cfg_rocket

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
		)

		self.driver = om.ScipyOptimizeDriver()
		self.driver.options["optimizer"] = "SLSQP"

		self.checks = checks

		# - Design variables

		# Store payload mass and target apogee as an instance attribute
		gl = cfg_rocket.cfg_global       if cfg_rocket else None
		ef = cfg_rocket.cfg_efficiencies if cfg_rocket else None
		op = cfg_rocket.cfg_optim        if cfg_rocket else None

		self.payload_mass = (
			payload_mass if payload_mass is not None
			else gl.payload_mass_kg
		)

		self.nonprop_mass = (
			nonprop_mass if nonprop_mass is not None
			else gl.nonprop_mass_kg
		)

		self.target_apogee = (
			target_apogee if target_apogee is not None
			else (gl.target_altitude_m if gl else 3100.0)
		)

		eff_apogee = self.target_apogee / ef.trajectory

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

		self.model.add_design_var(
			"OptimizationVars.o_nozzle_throat_area",
			lower = 1.0e-4,
			upper = 6.0e-4,
			ref   = 2.0e-4,
		)

		# - Constraints
		self.model.add_constraint(
			"apogee",
			lower = eff_apogee,
			ref   = eff_apogee,
		)

		self.model.add_constraint(
			"burn_time",
			lower = 5.0,
			upper = 15.0,
			ref   = 6.0,
		)

		self.model.add_constraint(
			"Propulsion.prop_thrust",
			upper = 1200.0,
			ref   = 1000.0,
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
		self.set_val("DesignVars.g_payload_mass", self.payload_mass, units="kg")
		self.set_val("DesignVars.g_nonprop_mass", self.nonprop_mass, units="kg")

		self.set_val("DesignVars.g_diameter",                 gl.diameter_m)
		self.set_val("DesignVars.press_diam",                 pr.diam_m)
		self.set_val("DesignVars.tank_pressure",              ox.pressure_bar)
		self.set_val("DesignVars.tank_diam",                  ox.diam_m)
		self.set_val("DesignVars.injector_cd",                inj.cd)
		self.set_val("DesignVars.fuel_port_diam",             fu.port_diam_m)
		self.set_val("DesignVars.fuel_reg_exponent",          fu.reg_exponent)
		self.set_val("DesignVars.fuel_reg_ref",               fu.reg_ref_ms)
		self.set_val("DesignVars.nozzle_expansion_ratio",     nz.expansion_ratio)

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
		print("")
		print(f"Apogee:                   \t{ap:{FMT}} m")
		print(f"Burn time:                \t{t_burn:{FMT}} s")
		print(f"Liftoff thrust:           \t{thr:{FMT}} N")
		print(f"Liftoff Isp:              \t{isp:{FMT}} s")
		print(f"Chamber pressure:         \t{pch:{FMT}} bar")
		print(f"Chamber flame temp:       \t{tch:{FMT}} K")
		print(f"Injector ΔP:              \t{dp:{FMT}} bar")
		print("")
		print(f"Dry mass:                 \t{mdry:{FMT}} kg")
		print(f"Pressurant mass:          \t{mpr:{FMT}} kg")
		print(f"Total mass at liftoff:    \t{mi:{FMT}} kg")
		print(f"TWR at launch:            \t{twr:{FMT}}")

	def print_parameters(self, path: str = "outputs/rocket.txt"):
		"""Dump all computed variables to an output file"""

		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, mode="wt") as f:
			self.model.list_outputs(
				val          = True,
				units        = True,
				hierarchical = True,
				out_stream   = f,
			)

	def print_graphs(self, out_dir: str = "figures", prefix: str = "rocket"):
		"""Draw all the connectivity graphs, provided Graphviz is installed"""

		if not has_graphviz():
			print(f"Graphviz ('dot') not found, skipping {prefix} graphs")
			return

		os.makedirs(out_dir, exist_ok=True)
		viewer = GraphViewer(self.model)
		for gtype in ["dataflow", "tree", "cycle"]:
			png_path = os.path.join(out_dir, f"{prefix}_{gtype}.png")
			svg_path = os.path.join(out_dir, f"{prefix}_{gtype}.svg")
			dot = viewer.write_graph(
				gtype     = gtype,
				display   = False,
				show_vars = True,
				#exclude   = ("_auto_ivc",),
				outfile   = png_path,
			)
			if dot is not None:
				match gtype:
					case "dataflow":
						# "spline" | "ortho" | "curved" | "line" | "polyline"
						splines = "spline" 
					case "tree":
						splines = "spline"
					case "cycle":
						splines = "spline"
				dot = style_graph(dot, splines=splines, concentrate=True)
				dot.write_png(png_path)

	def report(
		self,
		out_txt : str  = "outputs/rocket.txt",
		graphs  : bool = True,
	):
		"""Print results and generate output artifacts"""

		self.print_summary()
		self.print_parameters(out_txt)
		if graphs:
			self.print_graphs()
	#endregion
