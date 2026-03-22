"""DSO catalog: built-in constants (M, C) + lazy-loaded CSV catalogs."""
from __future__ import annotations

import csv
import importlib.resources
import logging
import re
from typing import Optional

from picer.objects.models import DeepSkyObject

logger = logging.getLogger(__name__)

# ── Messier (110 objects) ────────────────────────────────────────────────────
# (number, common_name, obj_type, constellation, ra_deg, dec_deg)  J2000
_MESSIER_RAW: list[tuple[int, str, str, str, float, float]] = [
    (1,   "Crab Nebula",           "Supernova Remnant",  "Tau",  83.633,   22.014),
    (2,   "",                      "Globular Cluster",   "Aqr", 323.363,   -0.823),
    (3,   "",                      "Globular Cluster",   "CVn", 205.548,   28.374),
    (4,   "",                      "Globular Cluster",   "Sco", 245.897,  -26.526),
    (5,   "",                      "Globular Cluster",   "Ser", 229.638,    2.081),
    (6,   "Butterfly Cluster",     "Open Cluster",       "Sco", 265.050,  -32.217),
    (7,   "Ptolemy Cluster",       "Open Cluster",       "Sco", 268.456,  -34.793),
    (8,   "Lagoon Nebula",         "Emission Nebula",    "Sgr", 270.924,  -24.383),
    (9,   "",                      "Globular Cluster",   "Oph", 259.799,  -18.516),
    (10,  "",                      "Globular Cluster",   "Oph", 254.288,   -4.100),
    (11,  "Wild Duck Cluster",     "Open Cluster",       "Sct", 282.767,   -6.272),
    (12,  "",                      "Globular Cluster",   "Oph", 251.809,   -1.948),
    (13,  "Hercules Cluster",      "Globular Cluster",   "Her", 250.423,   36.461),
    (14,  "",                      "Globular Cluster",   "Oph", 264.401,   -3.246),
    (15,  "",                      "Globular Cluster",   "Peg", 322.493,   12.167),
    (16,  "Eagle Nebula",          "Open Cluster",       "Ser", 274.700,  -13.807),
    (17,  "Omega Nebula",          "Emission Nebula",    "Sgr", 275.196,  -16.177),
    (18,  "",                      "Open Cluster",       "Sgr", 275.315,  -17.137),
    (19,  "",                      "Globular Cluster",   "Oph", 255.659,  -26.268),
    (20,  "Trifid Nebula",         "Emission Nebula",    "Sgr", 270.633,  -23.033),
    (21,  "",                      "Open Cluster",       "Sgr", 271.100,  -22.500),
    (22,  "Sagittarius Cluster",   "Globular Cluster",   "Sgr", 279.100,  -23.905),
    (23,  "",                      "Open Cluster",       "Sgr", 269.267,  -18.983),
    (24,  "Sagittarius Star Cloud","Star Cloud",         "Sgr", 274.200,  -18.400),
    (25,  "",                      "Open Cluster",       "Sgr", 277.938,  -19.250),
    (26,  "",                      "Open Cluster",       "Sct", 281.362,   -9.374),
    (27,  "Dumbbell Nebula",       "Planetary Nebula",   "Vul", 299.901,   22.721),
    (28,  "",                      "Globular Cluster",   "Sgr", 276.137,  -24.870),
    (29,  "",                      "Open Cluster",       "Cyg", 308.167,   38.533),
    (30,  "",                      "Globular Cluster",   "Cap", 325.091,  -23.180),
    (31,  "Andromeda Galaxy",      "Galaxy",             "And",  10.685,   41.269),
    (32,  "",                      "Galaxy",             "And",  10.675,   40.867),
    (33,  "Triangulum Galaxy",     "Galaxy",             "Tri",  23.462,   30.660),
    (34,  "",                      "Open Cluster",       "Per",  40.517,   42.747),
    (35,  "",                      "Open Cluster",       "Gem",  92.267,   24.333),
    (36,  "",                      "Open Cluster",       "Aur",  84.067,   34.133),
    (37,  "",                      "Open Cluster",       "Aur",  88.067,   32.550),
    (38,  "",                      "Open Cluster",       "Aur",  82.183,   35.833),
    (39,  "",                      "Open Cluster",       "Cyg", 323.133,   48.433),
    (40,  "Winnecke 4",            "Double Star",        "UMa", 185.560,   58.083),
    (41,  "",                      "Open Cluster",       "CMa", 101.500,  -20.733),
    (42,  "Orion Nebula",          "Emission Nebula",    "Ori",  83.822,   -5.391),
    (43,  "De Mairan's Nebula",    "Emission Nebula",    "Ori",  83.858,   -5.267),
    (44,  "Beehive Cluster",       "Open Cluster",       "Cnc", 130.100,   19.983),
    (45,  "Pleiades",              "Open Cluster",       "Tau",  56.750,   24.117),
    (46,  "",                      "Open Cluster",       "Pup", 115.442,  -14.817),
    (47,  "",                      "Open Cluster",       "Pup", 114.025,  -14.500),
    (48,  "",                      "Open Cluster",       "Hya", 123.417,   -5.767),
    (49,  "",                      "Galaxy",             "Vir", 187.444,    8.000),
    (50,  "",                      "Open Cluster",       "Mon", 105.700,   -8.317),
    (51,  "Whirlpool Galaxy",      "Galaxy",             "CVn", 202.470,   47.195),
    (52,  "",                      "Open Cluster",       "Cas", 344.767,   61.583),
    (53,  "",                      "Globular Cluster",   "Com", 198.223,   18.168),
    (54,  "",                      "Globular Cluster",   "Sgr", 283.764,  -30.479),
    (55,  "",                      "Globular Cluster",   "Sgr", 294.997,  -30.965),
    (56,  "",                      "Globular Cluster",   "Lyr", 289.149,   30.184),
    (57,  "Ring Nebula",           "Planetary Nebula",   "Lyr", 283.396,   33.029),
    (58,  "",                      "Galaxy",             "Vir", 189.430,   11.817),
    (59,  "",                      "Galaxy",             "Vir", 190.508,   11.647),
    (60,  "",                      "Galaxy",             "Vir", 190.917,   11.552),
    (61,  "",                      "Galaxy",             "Vir", 185.475,    4.474),
    (62,  "",                      "Globular Cluster",   "Oph", 255.303,  -30.112),
    (63,  "Sunflower Galaxy",      "Galaxy",             "CVn", 198.956,   42.029),
    (64,  "Black Eye Galaxy",      "Galaxy",             "Com", 194.182,   21.683),
    (65,  "",                      "Galaxy",             "Leo", 169.733,   13.092),
    (66,  "",                      "Galaxy",             "Leo", 170.062,   12.991),
    (67,  "",                      "Open Cluster",       "Cnc", 132.825,   11.817),
    (68,  "",                      "Globular Cluster",   "Hya", 189.867,  -26.744),
    (69,  "",                      "Globular Cluster",   "Sgr", 277.846,  -32.348),
    (70,  "",                      "Globular Cluster",   "Sgr", 280.804,  -32.292),
    (71,  "",                      "Globular Cluster",   "Sge", 298.443,   18.779),
    (72,  "",                      "Globular Cluster",   "Aqr", 313.358,  -12.537),
    (73,  "",                      "Asterism",           "Aqr", 314.742,  -12.633),
    (74,  "Phantom Galaxy",        "Galaxy",             "Psc",  24.174,   15.783),
    (75,  "",                      "Globular Cluster",   "Sgr", 301.520,    6.867),
    (76,  "Little Dumbbell Nebula","Planetary Nebula",   "Per",  25.578,   51.575),
    (77,  "",                      "Galaxy",             "Cet",  40.670,   -0.013),
    (78,  "",                      "Reflection Nebula",  "Ori",  86.683,    0.067),
    (79,  "",                      "Globular Cluster",   "Lep",  81.046,  -24.524),
    (80,  "",                      "Globular Cluster",   "Sco", 244.260,  -22.976),
    (81,  "Bode's Galaxy",         "Galaxy",             "UMa", 148.888,   69.065),
    (82,  "Cigar Galaxy",          "Galaxy",             "UMa", 148.969,   69.679),
    (83,  "Southern Pinwheel",     "Galaxy",             "Hya", 204.254,  -29.866),
    (84,  "",                      "Galaxy",             "Vir", 186.266,   12.887),
    (85,  "",                      "Galaxy",             "Com", 186.350,   18.191),
    (86,  "",                      "Galaxy",             "Vir", 186.556,   12.946),
    (87,  "Virgo A",               "Galaxy",             "Vir", 187.706,   12.391),
    (88,  "",                      "Galaxy",             "Com", 187.997,   14.420),
    (89,  "",                      "Galaxy",             "Vir", 188.916,   12.556),
    (90,  "",                      "Galaxy",             "Vir", 188.862,   13.163),
    (91,  "",                      "Galaxy",             "Com", 188.857,   14.497),
    (92,  "",                      "Globular Cluster",   "Her", 259.281,   43.136),
    (93,  "",                      "Open Cluster",       "Pup", 116.117,  -23.850),
    (94,  "Croc's Eye Galaxy",     "Galaxy",             "CVn", 192.721,   41.120),
    (95,  "",                      "Galaxy",             "Leo", 160.990,   11.704),
    (96,  "",                      "Galaxy",             "Leo", 161.690,   11.820),
    (97,  "Owl Nebula",            "Planetary Nebula",   "UMa", 168.699,   55.019),
    (98,  "",                      "Galaxy",             "Com", 183.452,   14.900),
    (99,  "",                      "Galaxy",             "Com", 184.707,   14.416),
    (100, "",                      "Galaxy",             "Com", 185.729,   15.822),
    (101, "Pinwheel Galaxy",       "Galaxy",             "UMa", 210.802,   54.349),
    (102, "Spindle Galaxy",        "Galaxy",             "Dra", 225.742,   55.763),
    (103, "",                      "Open Cluster",       "Cas",  23.342,   60.658),
    (104, "Sombrero Galaxy",       "Galaxy",             "Vir", 189.998,  -11.623),
    (105, "",                      "Galaxy",             "Leo", 161.956,   12.582),
    (106, "",                      "Galaxy",             "CVn", 184.740,   47.304),
    (107, "",                      "Globular Cluster",   "Oph", 248.133,  -13.054),
    (108, "",                      "Galaxy",             "UMa", 167.879,   55.674),
    (109, "",                      "Galaxy",             "UMa", 179.399,   53.375),
    (110, "",                      "Galaxy",             "And",  10.092,   41.685),
]

MESSIER: list[DeepSkyObject] = [
    DeepSkyObject(catalog="M", designation=f"M {n}", name=name, obj_type=typ,
                  constellation=con, ra_deg=ra, dec_deg=dec)
    for n, name, typ, con, ra, dec in _MESSIER_RAW
]

# ── Caldwell (109 objects) ───────────────────────────────────────────────────
_CALDWELL_RAW: list[tuple[int, str, str, str, float, float]] = [
    (1,   "NGC 188",              "Open Cluster",       "Cep",  11.798,   85.255),
    (2,   "NGC 40",               "Planetary Nebula",   "Cep",   3.350,   72.532),
    (3,   "NGC 4236",             "Galaxy",             "Dra", 184.272,   69.464),
    (4,   "NGC 7023",             "Reflection Nebula",  "Cep", 315.973,   68.171),
    (5,   "IC 342",               "Galaxy",             "Cam",  56.702,   68.096),
    (6,   "NGC 6543",             "Planetary Nebula",   "Dra", 269.639,   66.633),
    (7,   "NGC 2403",             "Galaxy",             "Cam", 114.214,   65.601),
    (8,   "NGC 559",              "Open Cluster",       "Cas",  22.458,   63.300),
    (9,   "Sh2-155",              "Emission Nebula",    "Cep", 340.767,   62.617),
    (10,  "NGC 663",              "Open Cluster",       "Cas",  26.567,   61.233),
    (11,  "NGC 7635",             "Emission Nebula",    "Cas", 350.179,   61.200),
    (12,  "NGC 6946",             "Galaxy",             "Cyg", 308.718,   60.154),
    (13,  "NGC 457",              "Open Cluster",       "Cas",  19.350,   58.283),
    (14,  "Double Cluster",       "Open Cluster",       "Per",  34.750,   57.133),
    (15,  "NGC 6826",             "Planetary Nebula",   "Cyg", 295.275,   50.525),
    (16,  "NGC 7243",             "Open Cluster",       "Lac", 333.558,   49.883),
    (17,  "NGC 147",              "Galaxy",             "Cas",   8.301,   48.508),
    (18,  "NGC 185",              "Galaxy",             "Cas",   9.742,   48.337),
    (19,  "IC 5146",              "Emission Nebula",    "Cyg", 328.375,   47.262),
    (20,  "North America Nebula", "Emission Nebula",    "Cyg", 314.750,   44.367),
    (21,  "NGC 4449",             "Galaxy",             "CVn", 187.038,   44.094),
    (22,  "NGC 7662",             "Planetary Nebula",   "And", 350.650,   42.542),
    (23,  "NGC 891",              "Galaxy",             "And",  35.639,   42.349),
    (24,  "NGC 1275",             "Galaxy",             "Per",  49.951,   41.512),
    (25,  "NGC 2419",             "Globular Cluster",   "Lyn", 114.535,   38.882),
    (26,  "NGC 4244",             "Galaxy",             "CVn", 184.374,   37.807),
    (27,  "NGC 6888",             "Emission Nebula",    "Cyg", 303.113,   38.355),
    (28,  "NGC 752",              "Open Cluster",       "And",  29.217,   37.683),
    (29,  "NGC 5005",             "Galaxy",             "CVn", 197.734,   37.059),
    (30,  "NGC 7331",             "Galaxy",             "Peg", 339.267,   34.416),
    (31,  "IC 405",               "Emission Nebula",    "Aur",  83.805,   34.267),
    (32,  "NGC 4631",             "Galaxy",             "CVn", 190.533,   32.541),
    (33,  "NGC 6992",             "Supernova Remnant",  "Cyg", 314.297,   31.717),
    (34,  "NGC 6960",             "Supernova Remnant",  "Cyg", 311.573,   30.717),
    (35,  "NGC 4889",             "Galaxy",             "Com", 194.990,   27.977),
    (36,  "NGC 4559",             "Galaxy",             "Com", 188.993,   27.958),
    (37,  "NGC 6885",             "Open Cluster",       "Vul", 303.404,   26.483),
    (38,  "NGC 4565",             "Galaxy",             "Com", 189.087,   25.987),
    (39,  "NGC 2392",             "Planetary Nebula",   "Gem", 112.292,   20.912),
    (40,  "NGC 3626",             "Galaxy",             "Leo", 170.017,   18.357),
    (41,  "Hyades",               "Open Cluster",       "Tau",  66.750,   15.867),
    (42,  "NGC 7006",             "Globular Cluster",   "Del", 315.373,   16.187),
    (43,  "NGC 7814",             "Galaxy",             "Peg",   0.821,   16.145),
    (44,  "NGC 7479",             "Galaxy",             "Peg", 346.236,   12.323),
    (45,  "NGC 5248",             "Galaxy",             "Boo", 204.382,    8.885),
    (46,  "NGC 2261",             "Reflection Nebula",  "Mon", 100.236,    8.741),
    (47,  "NGC 6934",             "Globular Cluster",   "Del", 308.533,    7.404),
    (48,  "NGC 2775",             "Galaxy",             "Cnc", 137.582,    7.038),
    (49,  "NGC 2237",             "Emission Nebula",    "Mon",  97.625,    4.950),
    (50,  "NGC 3242",             "Planetary Nebula",   "Hya", 155.858,  -18.638),
    (51,  "IC 1613",              "Galaxy",             "Cet",  16.199,    2.133),
    (52,  "NGC 4697",             "Galaxy",             "Vir", 192.149,   -5.801),
    (53,  "NGC 3115",             "Galaxy",             "Sex", 151.308,   -7.719),
    (54,  "NGC 2506",             "Open Cluster",       "Mon", 119.992,  -10.783),
    (55,  "NGC 7009",             "Planetary Nebula",   "Aqr", 315.973,  -11.362),
    (56,  "NGC 246",              "Planetary Nebula",   "Cet",  11.761,  -11.877),
    (57,  "NGC 6822",             "Galaxy",             "Sgr", 296.230,  -14.803),
    (58,  "NGC 2360",             "Open Cluster",       "CMa", 109.433,  -15.617),
    (59,  "NGC 3242",             "Planetary Nebula",   "Hya", 155.858,  -18.638),
    (60,  "NGC 4038",             "Galaxy",             "Crv", 180.471,  -18.867),
    (61,  "NGC 4039",             "Galaxy",             "Crv", 180.526,  -18.886),
    (62,  "NGC 247",              "Galaxy",             "Cet",  11.785,  -20.758),
    (63,  "Helix Nebula",         "Planetary Nebula",   "Aqr", 337.411,  -20.837),
    (64,  "NGC 2362",             "Open Cluster",       "CMa", 109.683,  -24.950),
    (65,  "NGC 253",              "Galaxy",             "Scl",  11.888,  -25.289),
    (66,  "NGC 5694",             "Globular Cluster",   "Hya", 219.901,  -26.539),
    (67,  "NGC 1097",             "Galaxy",             "For",  41.578,  -30.275),
    (68,  "NGC 6729",             "Reflection Nebula",  "CrA", 286.917,  -36.964),
    (69,  "NGC 6302",             "Planetary Nebula",   "Sco", 258.095,  -37.103),
    (70,  "NGC 300",              "Galaxy",             "Scl",  13.723,  -37.684),
    (71,  "NGC 2477",             "Open Cluster",       "Pup", 118.029,  -38.533),
    (72,  "NGC 55",               "Galaxy",             "Scl",   3.722,  -39.196),
    (73,  "NGC 1851",             "Globular Cluster",   "Col",  78.528,  -40.047),
    (74,  "NGC 3132",             "Planetary Nebula",   "Vel", 151.755,  -40.437),
    (75,  "NGC 6124",             "Open Cluster",       "Sco", 246.317,  -40.667),
    (76,  "NGC 6231",             "Open Cluster",       "Sco", 253.550,  -41.800),
    (77,  "Centaurus A",          "Galaxy",             "Cen", 201.365,  -43.019),
    (78,  "NGC 6541",             "Globular Cluster",   "CrA", 272.995,  -43.715),
    (79,  "NGC 3201",             "Globular Cluster",   "Vel", 154.403,  -46.412),
    (80,  "Omega Centauri",       "Globular Cluster",   "Cen", 201.697,  -47.480),
    (81,  "NGC 6352",             "Globular Cluster",   "Ara", 261.372,  -48.422),
    (82,  "NGC 6193",             "Open Cluster",       "Ara", 249.475,  -48.767),
    (83,  "NGC 4945",             "Galaxy",             "Cen", 196.362,  -49.468),
    (84,  "NGC 5286",             "Globular Cluster",   "Cen", 206.612,  -51.374),
    (85,  "IC 2391",              "Open Cluster",       "Vel", 130.250,  -53.067),
    (86,  "NGC 6397",             "Globular Cluster",   "Ara", 265.176,  -53.675),
    (87,  "NGC 1261",             "Globular Cluster",   "Hor",  48.068,  -55.217),
    (88,  "NGC 5823",             "Open Cluster",       "Cir", 226.104,  -55.600),
    (89,  "NGC 6087",             "Open Cluster",       "Nor", 244.717,  -57.917),
    (90,  "NGC 2867",             "Planetary Nebula",   "Car", 139.413,  -58.317),
    (91,  "NGC 3532",             "Open Cluster",       "Car", 166.397,  -58.650),
    (92,  "Eta Carinae Nebula",   "Emission Nebula",    "Car", 160.990,  -59.867),
    (93,  "NGC 6752",             "Globular Cluster",   "Pav", 287.717,  -59.985),
    (94,  "Jewel Box",            "Open Cluster",       "Cru", 193.400,  -60.367),
    (95,  "NGC 6025",             "Open Cluster",       "TrA", 240.850,  -60.517),
    (96,  "NGC 2516",             "Open Cluster",       "Car", 119.517,  -60.867),
    (97,  "NGC 3766",             "Open Cluster",       "Cen", 174.167,  -61.617),
    (98,  "NGC 4609",             "Open Cluster",       "Cru", 190.533,  -62.967),
    (99,  "Coalsack",             "Dark Nebula",        "Cru", 186.000,  -63.000),
    (100, "IC 2944",              "Emission Nebula",    "Cen", 172.050,  -63.033),
    (101, "NGC 6744",             "Galaxy",             "Pav", 287.440,  -63.857),
    (102, "IC 2602",              "Open Cluster",       "Car", 160.733,  -64.400),
    (103, "Tarantula Nebula",     "Emission Nebula",    "Dor",  84.676,  -69.101),
    (104, "NGC 362",              "Globular Cluster",   "Tuc",  15.808,  -70.849),
    (105, "NGC 4833",             "Globular Cluster",   "Mus", 194.874,  -70.877),
    (106, "47 Tucanae",           "Globular Cluster",   "Tuc",   6.023,  -72.081),
    (107, "NGC 6101",             "Globular Cluster",   "Aps", 245.050,  -72.200),
    (108, "NGC 4372",             "Globular Cluster",   "Mus", 182.990,  -72.660),
    (109, "NGC 3195",             "Planetary Nebula",   "Cha", 153.950,  -80.867),
]

CALDWELL: list[DeepSkyObject] = [
    DeepSkyObject(catalog="C", designation=f"C {n}", name=name, obj_type=typ,
                  constellation=con, ra_deg=ra, dec_deg=dec)
    for n, name, typ, con, ra, dec in _CALDWELL_RAW
]

# ── Lazy-loaded CSV catalogs ─────────────────────────────────────────────────

_NGC_DATA:   list[DeepSkyObject] | None = None
_IC_DATA:    list[DeepSkyObject] | None = None
_B_DATA:     list[DeepSkyObject] | None = None
_LDN_DATA:   list[DeepSkyObject] | None = None
_LBN_DATA:   list[DeepSkyObject] | None = None
_ABELL_DATA: list[DeepSkyObject] | None = None
_UGC_DATA:   list[DeepSkyObject] | None = None
_PGC_DATA:   list[DeepSkyObject] | None = None


def _open_data_csv(filename: str):
    pkg = importlib.resources.files("picer.objects.data")
    return (pkg / filename).open("r", encoding="utf-8", newline="")


def _load_ngc_ic() -> None:
    global _NGC_DATA, _IC_DATA
    ngc_rows: list[DeepSkyObject] = []
    ic_rows:  list[DeepSkyObject] = []
    try:
        with _open_data_csv("NGC.csv") as fh:
            reader = csv.DictReader(fh, delimiter=";")
            for row in reader:
                raw_name = row["Name"].strip()
                is_ic = raw_name.startswith("IC")
                catalog = "IC" if is_ic else "NGC"
                prefix_len = 2 if is_ic else 3   # "IC" = 2, "NGC" = 3
                num_str = raw_name[prefix_len:].lstrip("0") or "0"
                designation = f"{catalog} {num_str}"
                ra_deg = _parse_ra_hms(row.get("RA", "").strip())
                dec_deg = _parse_dec_dms(row.get("Dec", "").strip())
                if ra_deg is None or dec_deg is None:
                    continue
                dso = DeepSkyObject(
                    catalog=catalog,
                    designation=designation,
                    name=row.get("Common names", "").strip().split(",")[0].strip(),
                    obj_type=_normalize_type(row.get("Type", "").strip()),
                    constellation=row.get("Const", "").strip(),
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                )
                if is_ic:
                    ic_rows.append(dso)
                else:
                    ngc_rows.append(dso)
    except Exception as exc:
        logger.warning("Could not load NGC.csv: %s", exc)
    _NGC_DATA = ngc_rows
    _IC_DATA = ic_rows


def _load_barnard() -> None:
    global _B_DATA
    rows: list[DeepSkyObject] = []
    try:
        with _open_data_csv("barnard.csv") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ra_deg = _safe_float(row.get("ra_deg"))
                dec_deg = _safe_float(row.get("dec_deg"))
                if ra_deg is None or dec_deg is None:
                    continue
                rows.append(DeepSkyObject(
                    catalog="B",
                    designation=f"B {row['id'].strip()}",
                    name=row.get("name", "").strip(),
                    obj_type=row.get("type", "Dark Nebula").strip(),
                    constellation=row.get("const", "").strip(),
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                ))
    except Exception as exc:
        logger.warning("Could not load barnard.csv: %s", exc)
    _B_DATA = rows


def _load_lynds() -> None:
    global _LDN_DATA, _LBN_DATA
    ldn_rows: list[DeepSkyObject] = []
    lbn_rows: list[DeepSkyObject] = []
    try:
        with _open_data_csv("lynds.csv") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ra_deg = _safe_float(row.get("ra_deg"))
                dec_deg = _safe_float(row.get("dec_deg"))
                if ra_deg is None or dec_deg is None:
                    continue
                cat = row.get("catalog", "").strip().upper()
                if cat not in ("LDN", "LBN"):
                    continue
                dso = DeepSkyObject(
                    catalog=cat,
                    designation=f"{cat} {row['id'].strip()}",
                    name="",
                    obj_type="Dark Nebula" if cat == "LDN" else "Bright Nebula",
                    constellation=row.get("const", "").strip(),
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                )
                (ldn_rows if cat == "LDN" else lbn_rows).append(dso)
    except Exception as exc:
        logger.warning("Could not load lynds.csv: %s", exc)
    _LDN_DATA = ldn_rows
    _LBN_DATA = lbn_rows


def _load_abell() -> None:
    global _ABELL_DATA
    rows: list[DeepSkyObject] = []
    try:
        with _open_data_csv("abell.csv") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ra_deg = _safe_float(row.get("ra_deg"))
                dec_deg = _safe_float(row.get("dec_deg"))
                if ra_deg is None or dec_deg is None:
                    continue
                rows.append(DeepSkyObject(
                    catalog="Abell",
                    designation=f"Abell {row['id'].strip()}",
                    name=row.get("name", "").strip(),
                    obj_type=row.get("type", "Galaxy Cluster").strip(),
                    constellation=row.get("const", "").strip(),
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                ))
    except Exception as exc:
        logger.warning("Could not load abell.csv: %s", exc)
    _ABELL_DATA = rows


def _load_ugc() -> None:
    global _UGC_DATA
    rows: list[DeepSkyObject] = []
    try:
        with _open_data_csv("ugc.csv") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ra_deg = _safe_float(row.get("ra_deg"))
                dec_deg = _safe_float(row.get("dec_deg"))
                if ra_deg is None or dec_deg is None:
                    continue
                rows.append(DeepSkyObject(
                    catalog="UGC",
                    designation=f"UGC {row['id'].strip()}",
                    name=row.get("name", "").strip(),
                    obj_type="Galaxy",
                    constellation=row.get("const", "").strip(),
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                ))
    except Exception as exc:
        logger.warning("Could not load ugc.csv: %s", exc)
    _UGC_DATA = rows


def _load_pgc() -> None:
    global _PGC_DATA
    rows: list[DeepSkyObject] = []
    try:
        with _open_data_csv("pgc.csv") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    pgc_id = int(row["id"].strip())
                except (ValueError, KeyError):
                    continue
                if pgc_id > 73197:
                    break
                ra_deg = _safe_float(row.get("ra_deg"))
                dec_deg = _safe_float(row.get("dec_deg"))
                if ra_deg is None or dec_deg is None:
                    continue
                rows.append(DeepSkyObject(
                    catalog="PGC",
                    designation=f"PGC {pgc_id}",
                    name=row.get("name", "").strip(),
                    obj_type="Galaxy",
                    constellation=row.get("const", "").strip(),
                    ra_deg=ra_deg,
                    dec_deg=dec_deg,
                ))
    except Exception as exc:
        logger.warning("Could not load pgc.csv: %s", exc)
    _PGC_DATA = rows


# ── Public API ────────────────────────────────────────────────────────────────

_CATALOG_LABELS: dict[str, str] = {
    "M":     "Messier (M)",
    "C":     "Caldwell (C)",
    "NGC":   "NGC",
    "IC":    "IC",
    "B":     "Barnard (B)",
    "LDN":   "Lynds Dark (LDN)",
    "LBN":   "Lynds Bright (LBN)",
    "Abell": "Abell",
    "UGC":   "UGC",
    "PGC":   "PGC",
}

CATALOG_KEYS: list[str] = list(_CATALOG_LABELS.keys())


def catalog_label(key: str) -> str:
    return _CATALOG_LABELS.get(key, key)


def find_object(catalog: str, query: str) -> Optional[DeepSkyObject]:
    """Search *catalog* for *query*.

    Query may be a bare number ("42"), full designation ("M 42", "NGC 1952"),
    or a common name substring (case-insensitive).
    Returns the first match, or None.
    """
    q = query.strip()
    objects = _get_catalog(catalog)
    if not objects:
        return None
    # 1. Bare number
    if re.fullmatch(r"\d+", q):
        target = f"{catalog} {q}"
        for obj in objects:
            if obj.designation == target:
                return obj
    # 2. Exact designation (case-insensitive)
    q_upper = q.upper()
    for obj in objects:
        if obj.designation.upper() == q_upper:
            return obj
    # 3. Common name substring
    q_lower = q.lower()
    for obj in objects:
        if obj.name and q_lower in obj.name.lower():
            return obj
    return None


def _get_catalog(catalog: str) -> list[DeepSkyObject]:
    global _NGC_DATA, _IC_DATA, _B_DATA, _LDN_DATA, _LBN_DATA
    global _ABELL_DATA, _UGC_DATA, _PGC_DATA

    if catalog == "M":
        return MESSIER
    if catalog == "C":
        return CALDWELL
    if catalog in ("NGC", "IC"):
        if _NGC_DATA is None:
            _load_ngc_ic()
        return _NGC_DATA if catalog == "NGC" else (_IC_DATA or [])
    if catalog == "B":
        if _B_DATA is None:
            _load_barnard()
        return _B_DATA or []
    if catalog in ("LDN", "LBN"):
        if _LDN_DATA is None:
            _load_lynds()
        return _LDN_DATA if catalog == "LDN" else (_LBN_DATA or [])
    if catalog == "Abell":
        if _ABELL_DATA is None:
            _load_abell()
        return _ABELL_DATA or []
    if catalog == "UGC":
        if _UGC_DATA is None:
            _load_ugc()
        return _UGC_DATA or []
    if catalog == "PGC":
        if _PGC_DATA is None:
            _load_pgc()
        return _PGC_DATA or []
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


def _parse_ra_hms(s: str) -> float | None:
    """Convert "HH:MM:SS.s" to decimal degrees."""
    try:
        parts = s.replace(":", " ").split()
        h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return (h + m / 60.0 + sec / 3600.0) * 15.0
    except Exception:
        return None


def _parse_dec_dms(s: str) -> float | None:
    """Convert "+DD:MM:SS" or "-DD:MM:SS" to decimal degrees."""
    try:
        sign = -1.0 if s.startswith("-") else 1.0
        s2 = s.lstrip("+-")
        parts = s2.replace(":", " ").split()
        d, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return sign * (d + m / 60.0 + sec / 3600.0)
    except Exception:
        return None


_TYPE_MAP: dict[str, str] = {
    "Gx":   "Galaxy",
    "OC":   "Open Cluster",
    "GC":   "Globular Cluster",
    "EN":   "Emission Nebula",
    "RN":   "Reflection Nebula",
    "SNR":  "Supernova Remnant",
    "PN":   "Planetary Nebula",
    "DN":   "Dark Nebula",
    "Ast":  "Asterism",
    "Cl+N": "Cluster + Nebula",
    "EmN":  "Emission Nebula",
    "HII":  "HII Region",
    "*":    "Star",
    "D*":   "Double Star",
    "***":  "Triple Star",
    "Other":"Other",
}


def _normalize_type(raw: str) -> str:
    return _TYPE_MAP.get(raw, raw)
