# endpoint_ical_allday_demo.py — the "is this iCal date all-day?" decision of
# the friend-events reader, captured as pure Python and compiled to a Form
# recipe.
#
# An iCal DTSTART is all-day when its params carry VALUE=DATE, or when the value
# is a bare 8-char date (YYYYMMDD, no "T" time part). That choice — all-day vs a
# timed event — is a decision, not carrier, so it runs on the Form kernel
# (endpoint_ical_allday_demo.fk) with this Python as the value-identical
# fallback. Built from str_len / substring / str_eq so it mirrors the kernel
# ops exactly: has_str/has_char are the substring/char scans the kernel has no
# native `in` for. Returns 1 for all-day, 0 for a timed event.


def slen(s):
    return len(s)


def has_char(s, c, i):
    while i < slen(s):
        if s[i:i + 1] == c:
            return 1
        i += 1
    return 0


def has_str(s, sub, i):
    while i + slen(sub) <= slen(s):
        if s[i:i + slen(sub)] == sub:
            return 1
        i += 1
    return 0


def is_allday(value, params):
    if has_str(params, "VALUE=DATE", 0) == 1:
        return 1
    if slen(value) == 8:
        return 1 if has_char(value, "T", 0) == 0 else 0
    return 0


value = "20260615"
params = ""
result = is_allday(value, params)       # -> 1
