#region Imports
from dataclasses import dataclass
#endregion

#region Gas record
@dataclass(frozen=True)
class Gas:
	name          : str
	molar_mass    : float               # [kg/kmol]
	r_specific    : float               # [J/(kg*K)]
	gamma         : float               # Ratio of specific heats (cp / cv)
	coolprop_name : str   | None = None # Fluid identifier for CoolProp
	z_factor      : float        = 1.0  # Real gas compressibility factor
	t_crit_k      : float | None = None # Critical temperature [K]
	p_crit_pa     : float | None = None # Critical pressure [Pa]
	acentric      : float        = 0.0  # Pitzer acentric factor [-]

	@classmethod
	def from_config(cls, cfg) -> "Gas":
		return cls(
			name          = cfg.name,
			molar_mass    = cfg.molar_mass,
			r_specific    = cfg.r_specific,
			gamma         = cfg.gamma,
			coolprop_name = cfg.coolprop_name,
			z_factor      = cfg.z_factor,
			t_crit_k      = cfg.t_crit_k,
			p_crit_pa     = cfg.p_crit_pa,
			acentric      = cfg.acentric,
		)
#endregion
