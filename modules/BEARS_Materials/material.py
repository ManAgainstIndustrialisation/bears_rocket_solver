#region Imports
from dataclasses import dataclass
#endregion

#region Material record
@dataclass(frozen=True)
class Material:
	name              : str
	density           : float # [kg/m^3]
	yield_strength    : float # [Pa]
	ultimate_strength : float # [Pa]
	elastic_modulus   : float # [Pa]

	@classmethod
	def from_config(cls, cfg) -> "Material":
		return cls(
			name              = cfg.name,
			density           = cfg.density,
			yield_strength    = cfg.yield_strength,
			ultimate_strength = cfg.ultimate_strength,
			elastic_modulus   = cfg.elastic_modulus,
		)
#endregion
