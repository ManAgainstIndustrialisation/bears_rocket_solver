#!env/bin/python
"""
The rocket optimization script using OpenMDAO for the framework

@author:  Andrii
@license: GPL-3.0-or-later
"""

#region Imports
import argparse
import os
import numpy as np

import openmdao.utils.variable_table as vt
import openmdao.core.system          as sys_mod

from modules.Config import (
	load_configs,
	load_reactants,
	load_materials,
	load_fluids,
)

from modules.BEARS_Atmo      import BEARS_Atm
from modules.BEARS_Chem      import BEARS_Chem
from modules.BEARS_Materials import Material, Gas
from modules.BEARS_Vessels   import LayeredWall
from modules.BEARS_Rocket    import (
	RocketLaunchProblem,
	TestStandProblem,
	sweep_diameters,
	format_sweep_org_table,
)
#endregion

#region Helpers
def patch_variable_table():
	"""
	Dirty hack to prevent OpenMDAO from taking the Euclidean norm of array
	variables for the variable printout, since that makes no sense for this
	setup
	"""

	orig_write = vt.write_var_table

	def patched_write(
		pathname,
		var_list,
		var_type,
		var_dict,
		hierarchical = True,
		print_arrays = False,
		out_stream   = None,
	):
		patched = {}
		for k, meta in var_dict.items():
			meta_copy = dict(meta)
			val = meta_copy.get("val")
			if isinstance(val, np.ndarray) and val.size > 1:
				meta_copy["val"] = np.array2string(
					val, precision=6, separator=", "
				)
			patched[k] = meta_copy

		return orig_write(
			pathname, var_list, var_type, patched,
			hierarchical=hierarchical, print_arrays=print_arrays,
			out_stream=out_stream,
		)

	vt.write_var_table      = patched_write
	sys_mod.write_var_table = patched_write
#endregion

#region Main
def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--sweep",
		action = "store_true",
		help   = "run an airframe diameter parameter sweep after the solve",
	)
	args = parser.parse_args()

	patch_variable_table()

	#region Working directories
	work_dir = os.path.abspath("work")
	os.makedirs(work_dir, exist_ok=True)
	BEARS_Chem.set_work_dir(os.path.join(work_dir, "RocketCEA"))
	#endregion

	#region Inputs
	cfg_rocket = load_configs("inputs/rocket.toml")
	cfg_reac   = load_reactants("inputs/reactants.toml")

	atm  = BEARS_Atm(cfg_rocket.cfg_models.atmosphere)
	chem = BEARS_Chem.from_config(
		cfg_reac, backend=cfg_rocket.cfg_models.chemistry
	)

	cfg_mat    = load_materials("inputs/materials.toml")
	cfg_fluids = load_fluids("inputs/fluids.toml")

	materials = {m.id: Material.from_config(m) for m in cfg_mat.materials}
	gases     = {g.id: Gas.from_config(g) for g in cfg_fluids.gases}
	walls     = {
		w.id: LayeredWall.from_config(w, materials) for w in cfg_mat.walls
	}

	copv_ox    = walls["copv_ox"]
	copv_press = walls["copv_press"]
	press_gas  = gases["N2"]
	#endregion

	#region Rocket optimization
	prob_rocket = RocketLaunchProblem(
		atm                 = atm,
		chem                = chem,
		cfg_rocket          = cfg_rocket,
		ox_wall_material    = copv_ox,
		press_wall_material = copv_press,
		press_gas           = press_gas,
		reports             = True,
		work_dir            = work_dir,
	)

	prob_rocket.setup()
	prob_rocket.run()

	m_prop_opt = prob_rocket.get_val(
		"OptimizationVars.o_propellant_mass", units="kg"
	)[0]

	mr_opt = prob_rocket.get_val(
		"OptimizationVars.o_mixture_ratio"
	)[0]

	a_inj_opt = prob_rocket.get_val(
		"OptimizationVars.o_injector_area", units="mm**2"
	)[0]

	a_throat_opt = prob_rocket.get_val(
		"OptimizationVars.o_nozzle_throat_area", units="cm**2"
	)[0]

	eps_opt = prob_rocket.get_val(
		"DesignVars.nozzle_expansion_ratio"
	)[0]

	prob_rocket.report()
	#endregion

	print("--------")

	#region Test stand
	prob_stand = TestStandProblem(
		chem          = chem,
		run_tank_wall = walls["run_tank"],
		reports       = False,
	)

	prob_stand.setup()

	prob_stand.set_opt_vars(
		m_prop_kg       = m_prop_opt,
		mr              = mr_opt,
		a_inj_mm2       = a_inj_opt,
		a_throat_cm2    = a_throat_opt,
		expansion_ratio = eps_opt,
	)

	prob_stand.run()
	prob_stand.report()
	#endregion

	#region Diameter sweep
	if args.sweep:
		diams = [0.125, 0.140, 0.150, 0.160, 0.170]

		sweep_results = sweep_diameters(prob_rocket, diams)
		print("\nDiameter parameter sweep:")
		print(format_sweep_org_table(sweep_results))
	#endregion
#endregion

if __name__ == "__main__": main()
