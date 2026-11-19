#region Imports
import os

from openmdao.api import Group
from openmdao.visualization.graph_viewer import GraphViewer

from .graph_style import has_graphviz, style_graph
#endregion

def write_output_table(model: Group, path: str):
	"""Dump all computed model outputs to a text file"""

	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, mode="wt") as f:
		model.list_outputs(
			val          = True,
			units        = True,
			hierarchical = True,
			out_stream   = f,
		)

def write_graphs(
	model   : Group,
	out_dir : str,
	prefix  : str,
	style   : bool = True,
	splines : str  = "spline",
):
	"""Draw the model connectivity graphs, provided Graphviz is installed"""

	if not has_graphviz():
		print(f"Graphviz ('dot') not found, skipping {prefix} graphs")
		return

	os.makedirs(out_dir, exist_ok=True)
	viewer = GraphViewer(model)
	for gtype in ["dataflow", "tree", "cycle"]:
		png_path = os.path.join(out_dir, f"{prefix}_{gtype}.png")
		dot = viewer.write_graph(
			gtype     = gtype,
			display   = False,
			show_vars = True,
			outfile   = png_path,
		)
		if dot is not None:
			if style:
				# "spline" | "ortho" | "curved" | "line" | "polyline"
				dot = style_graph(dot, splines=splines, concentrate=True)
			dot.write_png(png_path)
