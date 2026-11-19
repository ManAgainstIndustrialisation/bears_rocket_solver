#region Imports
from .reac import Reactant
#endregion

def reactant_card(
	reactant : Reactant,
	fraction : float | None = None,
) -> str:
	"""
	Generate a CEA propellant card for a Reactant object, specifying the `wt%`
	fraction

	See <https://rocketcea.readthedocs.io/en/latest/std_examples.html>
	"""

	f = reactant.mass_fraction if fraction is None else fraction

	formula_comp = [
		f"{atom} {float(count)}" for atom, count in reactant.formula.items()
	]

	formula_str = " ".join(formula_comp)

	lines = []

	line1 = [
		f"{reactant.reactype}",
		f"{reactant.name}",
		f"{formula_str}",
		f"wt%={f}",
	]
	lines.append(" ".join(line1))

	line2 = [
		f"h,{reactant.enthalpy_units}={reactant.enthalpy}",
		f"t(k)={reactant.temperature}",
	]
	lines.append(" ".join(line2))

	return "\n".join(lines)

def gencard(components: tuple[Reactant]) -> str:
	"""
	Generate a CEA propellant card from a list of reactants, weighing each
	reactant appropriately according to its `mass_fraction` field

	Same thing as `reactant_card` but for lists

	See <https://rocketcea.readthedocs.io/en/latest/std_examples.html>
	"""

	rt = components[0].reactype
	if not all(r.reactype == rt for r in components):
		raise ValueError(
			"Can only generate a composite card for reactants of the same type"
		)

	wt_total = sum(comp.mass_fraction for comp in components)

	if len(components) == 1:
		ret = reactant_card(components[0], fraction=100.0)
	else:
		cards = []
		for comp in components:
			wt = (comp.mass_fraction / wt_total) * 100.0
			# NOTE: Component weights must add up to 100.0 for CEA

			cards.append(reactant_card(comp, fraction=wt))

		ret = "\n".join(cards)
	
	return ret

def bulk_density(reactants: tuple[Reactant, ...]) -> float:
	"""Effective bulk density in kg/m^3 for a list of reactants"""
	wt_total = sum(r.mass_fraction for r in reactants)
	inv_rho = sum(
		(r.mass_fraction / wt_total) / r.get_density_si() for r in reactants
	)
	return 1.0 / inv_rho

def to_cea_reactant(r: Reactant):
	"""Convert Reactant into a NASA CEA Reactant object"""

	import cea

	if r.enthalpy is not None and r.enthalpy_units is not None:
		u = r.enthalpy_units.lower()
		ret = cea.Reactant(
			name           = r.name,
			formula        = r.formula or None,
			enthalpy       = r.enthalpy,
			enthalpy_units = u,
			temperature    = r.temperature,
		)
	elif r.formula:
		ret = cea.Reactant(
			name        = r.name,
			formula     = r.formula,
			temperature = r.temperature,
		)
	else:
		ret = cea.Reactant(name = r.name, temperature = r.temperature)

	return ret
