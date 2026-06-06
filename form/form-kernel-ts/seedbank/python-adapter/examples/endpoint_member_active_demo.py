# endpoint_member_active_demo.py — the membrane's see-lock decision, captured
# as pure Python and compiled to a Form recipe.
#
# household-membrane.form: (lock (see open-to active-member)). The roster is
# the cells actually here — status "active", not "invited". Whether a member
# is active is a decision, so it runs on the Form kernel with this Python as
# the value-identical fallback. Returns 1 for active, 0 otherwise.


def is_active(status):
    return 1 if status == "active" else 0


status = "active"
result = is_active(status)       # -> 1
