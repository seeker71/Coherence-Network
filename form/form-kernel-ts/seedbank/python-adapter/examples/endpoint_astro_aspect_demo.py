# endpoint_astro_aspect_demo.py — the first modality numeric recipe, captured
# as pure Python and compiled to a Form recipe.
#
# A natal chart is the EDGES between a person-cell and the planet-cells
# (modality-lattices.form). The simplest numeric insight over those edges is
# the ASPECT: the angular relationship between two positions — which is itself
# the edge between two planet-cells turned into a number. Given two ecliptic
# longitudes in whole degrees (0..359) and an orb, `aspect` returns the major
# aspect that holds between them, or -1 for none. This runs on the kernel via
# serve_via_kernel, three-way (CPython / TS / Rust) parity the gate, with this
# Python as the value-identical fallback. The reading stays human; the body
# only computes the geometry.
#
# Encoding — numbers are the substrate's native tongue:
#   aspect: conjunction=0  sextile=1  square=2  trine=3  opposition=4  none=-1
#   separation is folded to [0, 180]; "within orb" means |sep - target| <= orb.


def absv(x):
    return -x if x < 0 else x


def sep(a, b):                      # angular separation, folded to [0, 180]
    d = absv(a - b)
    return 360 - d if d > 180 else d


def within(d, target, orb):         # |d - target| <= orb  (integer: < orb+1)
    return absv(d - target) < (orb + 1)


def aspect(a, b, orb):
    d = sep(a, b)
    if within(d, 0, orb):
        return 0                    # conjunction
    if within(d, 60, orb):
        return 1                    # sextile
    if within(d, 90, orb):
        return 2                    # square
    if within(d, 120, orb):
        return 3                    # trine
    if within(d, 180, orb):
        return 4                    # opposition
    return -1                       # no major aspect


a = 13
b = 133
orb = 6
result = aspect(a, b, orb)          # 120° apart → trine → 3
