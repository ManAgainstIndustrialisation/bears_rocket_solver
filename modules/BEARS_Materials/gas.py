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
			name       = cfg.name,
			molar_mass = cfg.molar_mass,
			r_specific = cfg.r_specific,
			gamma      = cfg.gamma,
			z_factor   = cfg.z_factor,
			coolprop_name = getattr(cfg, "coolprop_name", None),
			t_crit_k      = getattr(cfg, "t_crit_k",      None),
			p_crit_pa     = getattr(cfg, "p_crit_pa",     None),
			acentric      = getattr(cfg, "acentric",      0.0),
		)
#endregion

#region Standard presets
NITROGEN = Gas(
	name          = "Nitrogen Gas",
	coolprop_name = "N2",
	molar_mass    = 28.0134,
	r_specific    = 296.8,
	gamma         = 1.40,
	z_factor      = 1.15,
	t_crit_k      = 126.192,
	p_crit_pa     = 33.958e5,
	acentric      = 0.0372,
)

HELIUM = Gas(
	name          = "Helium Gas",
	coolprop_name = "He",
	molar_mass    = 4.0026,
	r_specific    = 2077.2,
	gamma         = 1.667,
	z_factor      = 1.05,
	t_crit_k      = 5.1953,
	p_crit_pa     = 2.2746e5,
	acentric      = -0.390,
)
#endregion
