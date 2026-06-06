# endpoint_placeholder_name_demo.py — the "is this a placeholder name?"
# decision of the household membrane, captured as pure Python and compiled to
# a Form recipe.
#
# A role-only invite carries "New {role}" until the newcomer claims their own
# name on first open (household-membrane.form: bind ?token ?self-name). Whether
# a name is still that placeholder — empty, or beginning "New " — is a decision,
# not carrier, so it runs on the Form kernel with this Python as the value-
# identical fallback. Returns 1 for placeholder, 0 for a real name. Built only
# from str_len / substring / str_eq so it mirrors the kernel ops exactly.


def slen(s):
    return len(s)


def str_eq(a, b):
    return a == b


def starts(s, p):
    if slen(s) < slen(p):
        return 0
    return 1 if str_eq(s[0:slen(p)], p) else 0


def is_placeholder(name):
    if slen(name) == 0:
        return 1
    return starts(name, "New ")


name = "New resident"
result = is_placeholder(name)       # -> 1
