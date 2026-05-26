# Auto-emitted by form/form-stdlib/emits/python-native.fk
# Hand edits will be overwritten; edit the Form source instead.
from kernels.python_bmf import sdk

def cap_empty(_x):
    return []

def cap_pair(name, value):
    return [name, value]

def cap_name(p):
    return p[0]

def cap_value(p):
    return p[1:][0]

def cap_get(caps, name):
    return ([] if (len(caps) == 0) else (cap_value(caps[0]) if (cap_name(caps[0]) == name) else cap_get(caps[1:], name)))

def cap_set(caps, name, value):
    return [cap_pair(name, value), *caps]

def cap_merge(a, b):
    return (a if (len(b) == 0) else cap_merge([b[0], *a], b[1:]))

def mk_match(caps, rest):
    return ["match", caps, rest]

def mk_fail(reason):
    return ["fail", reason]

def match_p(r):
    return (r[0] == "match")

def fail_p(r):
    return (r[0] == "fail")