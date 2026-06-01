# endpoint_idea_marginal_from_record_demo.py — the marginal-CC-return core of
# idea_scoring._marginal_cc_return, but reading its inputs from a STRUCTURED
# OBJECT instead of six separate scalar arguments. The first transmuted route
# to exercise structure access: a recipe that receives a record (a dict / model
# the bridge marshals) and pulls named fields out of it via subscript.
#
# Method B marginal CC return: (value_gap * conf^2) / (remaining_cost + rr*0.5)
# where value_gap = max(pv - av, 0.0) and remaining_cost = max(ec - ac, 0.1) —
# uncaptured value per remaining CC, confidence discounted twice. The arithmetic
# is byte-identical to endpoint_marginal_cc_return_demo (the six-scalar twin);
# what is NEW here is that the six inputs arrive as fields of one object:
#   obj["potential_value"], obj["actual_value"], obj["confidence"],
#   obj["estimated_cost"], obj["actual_cost"], obj["resistance_risk"].
#
# The subscript reads lower to the kernel's record field access (Python
# `obj[k]` → the python-bmf SUBSCRIPT arm, which reads a string-keyed map). At
# request time the live route hands the recipe a record binding marshalled from
# a Python dict / model — form_kernel_bridge._fk_literal renders the dict as a
# `(record_new ...)` literal (subprocess path) and lib.rs py_to_value marshals
# it to a kernel Record (inline path). This `.py` proves the recipe BODY is
# three-way correct over a frozen sample object; the bridge marshalling is
# proven by the Python bridge tests (test_form_kernel_bridge_structure_access).
#
# round(_, 6) keeps the result on the shared decimal grid so all three runtimes
# print it identically (the float-print divergence the bands document never
# enters), via the round_ndigits native (PR #2320).
#
# max as comparison: the kernel `max` native floors floats; an `if a < b`
# branch is float-correct and value-identical, exactly as idea_score /
# grounded_roi do.


def marginal_from_idea(idea):
    pv = idea["potential_value"]
    av = idea["actual_value"]
    conf = idea["confidence"]
    ec = idea["estimated_cost"]
    ac = idea["actual_cost"]
    rr = idea["resistance_risk"]
    value_gap = pv - av
    if value_gap < 0.0:
        value_gap = 0.0
    remaining_cost = ec - ac
    if remaining_cost < 0.1:
        remaining_cost = 0.1
    return round((value_gap * conf * conf) / (remaining_cost + rr * 0.5), 6)


# Endpoint's frozen sample input — one idea as a structured object. value_gap =
# 8.0 - 3.0 = 5.0; remaining_cost = 4.0 - 1.0 = 3.0; result =
# round((5.0 * 0.64) / (3.0 + 1.0), 6) = round(3.2 / 4.0, 6) = 0.8.
idea = {
    "potential_value": 8.0,
    "actual_value": 3.0,
    "confidence": 0.8,
    "estimated_cost": 4.0,
    "actual_cost": 1.0,
    "resistance_risk": 2.0,
}

marginal_from_idea(idea)
