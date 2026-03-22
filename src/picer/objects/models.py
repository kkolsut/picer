"""Deep Sky Object data model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeepSkyObject:
    catalog: str        # "M","C","NGC","IC","B","LDN","LBN","Abell","UGC","PGC"
    designation: str    # "M 42", "NGC 1952"
    name: str           # "Orion Nebula" or ""
    obj_type: str       # "Emission Nebula", "Galaxy", …
    constellation: str  # IAU 3-letter abbreviation, e.g. "Ori"
    ra_deg: float       # RA J2000, decimal degrees [0, 360)
    dec_deg: float      # Dec J2000, decimal degrees [-90, +90]
