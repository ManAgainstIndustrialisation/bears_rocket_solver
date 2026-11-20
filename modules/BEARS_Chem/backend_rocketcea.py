#region Imports
from typing import TYPE_CHECKING

from ..Config import CONSTANTS

if TYPE_CHECKING: from .reac import Reactant
#endregion

PA_TO_PSIA = 1.450377e-4 # 1 Pa = 1.45038e-4 psia

class RocketCEABackend:
	"""RocketCEA backend wrapping Fortran CEA2"""

	def __init__(
		self,
		ox_reactants   : tuple["Reactant", ...],
		fuel_reactants : tuple["Reactant", ...],
	):
		from rocketcea.cea_obj     import CEA_Obj, add_new_fuel, add_new_oxidizer
		from rocketcea.input_cards import oxCards, fuelCards
		from .helpers              import gencard

		reac_cards = {"oxid": oxCards, "fuel": fuelCards}
		rnames : dict[str, str] = {}
		for rtype, rlist in [("oxid", ox_reactants), ("fuel", fuel_reactants)]:
			rname = "_".join([reac.name for reac in rlist])
			if rname not in reac_cards[rtype]:
				card = gencard(rlist)
				if rtype == "fuel": add_new_fuel(rname, card)
				else:               add_new_oxidizer(rname, card)
			rnames[rtype] = rname

		self._cea = CEA_Obj(oxName=rnames["oxid"], fuelName=rnames["fuel"])

	def get_chamber_gas(self, pc_pa: float, mr: float) -> tuple[float, float]:
		"""Chamber gas (molar mass [kg/kmol], ratio of specific heats)"""
		mw, gamma = self._cea.get_Chamber_MolWt_gamma(Pc=pc_pa * PA_TO_PSIA, MR=mr)
		return float(mw), float(gamma)

	def get_tcomb(self, pc_pa: float, mr: float) -> float:
		return self._cea.get_Tcomb(Pc=pc_pa * PA_TO_PSIA, MR=mr) * (5.0 / 9.0)

	def get_isp(
		self,
		pc_pa    : float,
		mr       : float,
		eps      : float,
		p_amb_pa : float = CONSTANTS.atmosphere.sea_level_pressure,
	) -> float:
		pc_psia = pc_pa * PA_TO_PSIA

		if p_amb_pa > 0.0:
			isp, _ = self._cea.estimate_Ambient_Isp(
				Pc=pc_psia, MR=mr, eps=eps, Pamb=p_amb_pa * PA_TO_PSIA
			)
			ret = float(isp)
		else:
			ret = float(self._cea.get_Isp(Pc=pc_psia, MR=mr, eps=eps))

		return ret
