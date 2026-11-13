# region Imports
from typing import override
from openmdao.api import ExplicitComponent
# endregion

class MassComponent(ExplicitComponent):

	def setup(self):
		self.add_input("diameter",          val=0.125, units="m")
		self.add_input("ref_diameter",      val=0.125, units="m")
		self.add_input("payload_mass",      val=2.0,   units="kg")
		self.add_input("nonprop_mass",      val=5.0,   units="kg")
		self.add_input("propellant_mass",   val=10.0,  units="kg")
		self.add_input("pressurant_mass",   val=0.5,   units="kg")

		self.add_input("ox_tank_mass",      val=2.0,   units="kg")
		self.add_input("press_tank_mass",   val=2.0,   units="kg")
		self.add_input("motor_dry_mass",    val=4.0,   units="kg")
		self.add_input("eta_prop",          val=1.0)

		self.add_output("structural_mass",  val=18.0,  units="kg")
		self.add_output("dry_mass",         val=20.0,  units="kg")
		self.add_output("initial_mass",     val=40.0,  units="kg")
		self.add_output("prop_loaded_mass", val=10.0,  units="kg")
		self.add_output("residual_mass",    val=10.0,  units="kg")

	def setup_partials(self):
		self.declare_partials("*", "*", method="cs")

	def compute(self, inputs, outputs):
		m_ox  = inputs["ox_tank_mass"]
		m_pr  = inputs["press_tank_mass"]
		m_mot = inputs["motor_dry_mass"]
		m_np  = inputs["nonprop_mass"]
		d_1   = inputs["diameter"]
		d_0   = inputs["ref_diameter"]

		m_prop    = inputs["propellant_mass"]
		m_press   = inputs["pressurant_mass"]
		m_payload = inputs["payload_mass"]

		m_nonprop = m_np * (d_1/d_0)
		m_struct = (m_ox + m_pr + m_mot + m_nonprop)

		eta_prop   = inputs["eta_prop"]
		m_loaded   = m_prop / eta_prop
		m_residual = m_loaded - m_prop

		m_dry  = m_payload + m_struct + m_residual
		m_init = m_dry + m_prop + m_press

		outputs["structural_mass"]  = m_struct
		outputs["dry_mass"]         = m_dry
		outputs["initial_mass"]     = m_init
		outputs["prop_loaded_mass"] = m_loaded
		outputs["residual_mass"]    = m_residual
