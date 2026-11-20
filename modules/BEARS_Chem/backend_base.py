#region Imports
from typing import Protocol, runtime_checkable

from ..Config import CONSTANTS
#endregion

@runtime_checkable
class ThermochemistryBackend(Protocol):
	"""Abstract protocol for chemical equilibrium backends"""

	def get_chamber_gas(self, pc_pa: float, mr: float) -> tuple[float, float]:
		"""Chamber gas (molar mass [kg/kmol], ratio of specific heats)"""
		...

	def get_tcomb(self, pc_pa: float, mr: float) -> float:
		...

	def get_isp(
		self,
		pc_pa    : float,
		mr       : float,
		eps      : float,
		p_amb_pa : float = CONSTANTS.atmosphere.sea_level_pressure,
	) -> float:
		...
