#region Imports
from ..BEARS_Chem      import BEARS_Chem
from ..BEARS_Materials import Gas
from ..BEARS_Vessels   import LayeredWall

from .group_teststand_flight import TestStandFlightGroup
from .prob_teststand         import TestStandProblem
#endregion

class TestStandFlightProblem(TestStandProblem):
	"""
	Test stand problem that can be fed either by the facility run tank or by
	the flight oxidizer and pressurant tanks (`tank_mode="flight"`)
	"""

	def __init__(
		self,
		chem           : BEARS_Chem,
		tank_mode      : str = "facility",
		run_tank_wall  : LayeredWall | None = None,
		ox_wall_mat    : LayeredWall | None = None,
		press_wall_mat : LayeredWall | None = None,
		press_gas      : Gas         | None = None,
		**kwargs,
	):
		model = TestStandFlightGroup(
			chem           = chem,
			tank_mode      = tank_mode,
			run_tank_wall  = run_tank_wall,
			ox_wall_mat    = ox_wall_mat,
			press_wall_mat = press_wall_mat,
			press_gas      = press_gas,
		)

		super().__init__(chem, model=model, **kwargs)

		self.tank_mode = tank_mode

	def set_tank_vals(self):
		match self.tank_mode:
			case "facility":
				super().set_tank_vals()
			case "flight":
				# Tank pressures come from sensors PT2 (oxidizer) and PT4 (N2)
				self.set_val("Sensors.PT2_run_tank_pressure",  60.0,  units="bar")
				self.set_val("Sensors.PT4_N2_supply_pressure", 200.0, units="bar")
				self.set_val("tank_diam",           0.12, units="m")
				self.set_val("tank_ullage_frac",    0.10)
				self.set_val("tank_safety_factor",  1.5)
				self.set_val("press_diam",          0.10, units="m")
				self.set_val("press_safety_factor", 1.5)
				self.set_val("tank_vapor_pressure", 63.08, units="bar")
