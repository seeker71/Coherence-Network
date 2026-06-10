# python_dict_demo.py — dict literals, subscript, membership, iteration,
# subscript-assign through the full Python -> Form -> native-kernel
# pipeline. Closes the "kernel can't return {key: value}" gap that's
# kept all but one FastAPI endpoint from transmuting.
#
# Runs identically under:
#   python3 python_dict_demo.py             - CPython
#   kernel-bmf-run <file.py>       - Form-native walker
#   form-kernel-rust python_dict_demo.fk    - native kernel binary
#
# The final expression is reduced to a scalar so parity comparison stays
# unambiguous regardless of how each runtime renders a dict literal.

def score_response(payload):
    # Build a dict from incoming fields - the actual shape most
    # FastAPI endpoints want to construct on the way out.
    out = {"signal": payload["signal"], "vitality": payload["vitality"]}
    out["weighted"] = out["signal"] * 3 + out["vitality"] * 2
    return out

# Build a payload dict; nested int and string values.
req = {"signal": 7, "vitality": 11}
resp = score_response(req)

# Subscript-read each field.
s = resp["signal"]
v = resp["vitality"]
w = resp["weighted"]

# Membership: `key in dict` returns True/False.
has_w = "weighted" in resp
has_x = "missing" in resp

# Iterate keys - dict iteration yields keys in insertion order.
key_chars = 0
for k in resp:
    key_chars = key_chars + len(k)

# Subscript-assign a new entry; len(dict) reports pair count.
resp["scope"] = 4
n_keys = len(resp)

# Reduce everything to a single integer so the parity gate compares
# rendered output unambiguously across runtimes:
#   s=7, v=11, w=7*3+11*2=43
#   has_w=True->1, has_x=False->0
#   key_chars = len("signal")+len("vitality")+len("weighted") = 6+8+8 = 22
#   n_keys=4
# total = 7 + 11 + 43 + 1 + 0 + 22 + 4 = 88
s + v + w + (1 if has_w else 0) + (1 if has_x else 0) + key_chars + n_keys
