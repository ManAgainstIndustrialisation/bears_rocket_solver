#region Imports
from openmdao.api import Group, Problem

from ..BEARS_Chem    import BEARS_Chem
from ..BEARS_Vessels import LayeredWall

from .group_teststand import TestStandGroup
from .reporting       import write_output_table, write_graphs
from .checks          import CheckFn, DEFAULT_TESTSTAND_CHECKS, run_checks
#endregion

class TestStandProblem(Problem):

	def __init__(
		self,
		chem          : BEARS_Chem,
		run_tank_wall : LayeredWall | None = None,
		checks        : tuple[CheckFn, ...] = DEFAULT_TESTSTAND_CHECKS,
		model         : Group | None = None,
		**kwargs,
	):
		"""`run_tank_wall` is required unless a prebuilt `model` is given"""
		if model is None:
			model = TestStandGroup(chem=chem, run_tank_wall=run_tank_wall)

		super().__init__(model=model, **kwargs)

		self.chem   = chem
		self.checks = checks

	def setup(self, **kwargs):
		super().setup(**kwargs)
		self.set_tank_vals()
		self.set_engine_vals()
		return self

	def set_tank_vals(self):
		# Run tank (pressure from sensor PT2)
		self.set_val("Sensors.PT2_run_tank_pressure", 60.0,  units="bar")
		self.set_val("run_tank_diam",                 0.15,  units="m")
		self.set_val("run_tank_ullage_frac",          0.08)
		self.set_val("run_tank_fluid_mass",           10.0,  units="kg")

	def set_engine_vals(self):
		# Engine baseline parameters
		self.set_val("test_prop_mass_init",    8.0,    units="kg")
		self.set_val("test_mixture_ratio",     6.618)
		self.set_val("injector_area",          1.5e-5, units="m**2")
		self.set_val("injector_cd",            0.70)
		self.set_val("fuel_port_diam",         0.05,   units="m")
		self.set_val("fuel_reg_exponent",      0.50)
		self.set_val("fuel_reg_ref",           1.0e-4, units="m/s")
		self.set_val("nozzle_throat_area",     2.0e-4, units="m**2")
		self.set_val("nozzle_expansion_ratio", 5.0)
		self.set_val("nozzle_length",          0.15,   units="m")
		self.set_val("nozzle_eta_friction",    0.95)

	def set_opt_vars(
		self,
		m_prop_kg       : float | None = None,
		mr              : float | None = None,
		a_inj_mm2       : float | None = None,
		a_throat_cm2    : float | None = None,
		expansion_ratio : float | None = None,
	):
		if m_prop_kg is not None:
			self.set_val("test_prop_mass_init",    m_prop_kg,    units="kg")
		if mr is not None:
			self.set_val("test_mixture_ratio",     mr)
		if a_inj_mm2 is not None:
			self.set_val("injector_area",          a_inj_mm2,    units="mm**2")
		if a_throat_cm2 is not None:
			self.set_val("nozzle_throat_area",     a_throat_cm2, units="cm**2")
		if expansion_ratio is not None:
			self.set_val("nozzle_expansion_ratio", expansion_ratio)

	def run(self):
		self.run_model()
		return self

	#region Verification
	def verify(self, raise_on_error : bool = True):
		return run_checks(self, self.checks, raise_on_error=raise_on_error)
	#endregion

	#region Outputs
	def print_summary(self):

		FMT = "8.3f"

		self.verify()

		sensor = lambda name, units: self.get_val(f"Sensors.{name}", units=units)[0]

		pt1 = sensor("PT1_N2O_supply_pressure", "bar")
		tc1 = sensor("TC1_N2O_supply_temp",     "K")
		pt2 = sensor("PT2_run_tank_pressure",   "bar")
		tc2 = sensor("TC2_run_liquid_temp",     "K")
		pt4 = sensor("PT4_N2_supply_pressure",  "bar")
		tc4 = sensor("TC4_run_dome_temp",       "K")
		pt3 = self.get_val("test_chamber_pressure_PT3", units="bar")[0]
		tc3 = self.get_val("test_chamber_temp_TC3",     units="K")[0]
		thr = self.get_val("test_thrust",               units="N")[0]
		isp = self.get_val("test_isp",                  units="s")[0]

		print("Simulating test stand:")
		print("")
		print(f"PT1 (N2O supply pressure):      \t{pt1:{FMT}} bar")
		print(f"TC1 (N2O supply temperature):   \t{tc1:{FMT}} K")
		print("")
		print(f"PT2 (run tank pressure):        \t{pt2:{FMT}} bar")
		print(f"TC2 (run tank liquid temp):     \t{tc2:{FMT}} K")
		print("")
		print(f"PT3 (chamber pressure):         \t{pt3:{FMT}} bar")
		print(f"TC3 (chamber flame temp):       \t{tc3:{FMT}} K")
		print("")
		print(f"PT4 (N2 supply pressure):       \t{pt4:{FMT}} bar")
		print(f"TC4 (run tank dome temp):       \t{tc4:{FMT}} K")
		print("")
		print(f"ΔP:                             \t{pt2 - pt3:{FMT}} bar")
		print(f"Thrust:                         \t{thr:{FMT}} N")
		print(f"Isp:                            \t{isp:{FMT}} s")

	def print_parameters(self, path: str = "outputs/teststand.txt"):
		write_output_table(self.model, path)

	def print_graphs(
		self,
		out_dir : str = "figures",
		prefix  : str = "teststand",
	):
		write_graphs(self.model, out_dir, prefix, style=False)

	def report(
		self,
		out_txt : str  = "outputs/teststand.txt",
		graphs  : bool = True,
	):
		self.print_summary()
		self.print_parameters(out_txt)
		if graphs: self.print_graphs()
	#endregion
