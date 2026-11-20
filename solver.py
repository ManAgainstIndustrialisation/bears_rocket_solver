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

from modules.Config       import load_rocket_inputs, load_materials
from modules.BEARS_Atmo   import BEARS_Atm
from modules.BEARS_Chem   import BEARS_Chem
from modules.BEARS_Thermo import create_pressurant_thermo
from modules.BEARS_Rocket import (
	RocketLaunchProblem,
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
		help   = "re-optimize over the [sweep] airframe diameters after the solve",
	)
	args = parser.parse_args()

	patch_variable_table()

	#region Working directories
	work_dir = os.path.abspath("work")
	os.makedirs(work_dir, exist_ok=True)
	BEARS_Chem.set_work_dir(os.path.join(work_dir, "RocketCEA"))
	#endregion

	#region Inputs and models
	cfg = load_rocket_inputs("inputs/rocket_inputs.toml")
	mat = load_materials("inputs/materials.toml")

	models = cfg.cfg_models
	ox     = cfg.cfg_oxy_tank
	pr     = cfg.cfg_press_tank
	#endregion

	#region Rocket optimization
	prob = RocketLaunchProblem(
		cfg          = cfg,
		atm          = BEARS_Atm(models.atmosphere, mat.air),
		chem         = BEARS_Chem(mat.propellants, models.chemistry),
		ox_wall      = mat.wall(ox.wall),
		press_wall   = mat.wall(pr.wall),
		press_gas    = mat.gas(pr.gas),
		press_thermo = create_pressurant_thermo(models.pressurant_thermo, pr.mass_margin),
		reports      = True,
		work_dir     = work_dir,
	)

	prob.setup()
	prob.run()
	prob.report()
	#endregion

	#region Diameter sweep
	if args.sweep:
		print("\nDiameter parameter sweep:")
		print(format_sweep_org_table(sweep_diameters(prob)))
	#endregion
#endregion

if __name__ == "__main__": main()
