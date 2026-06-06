# endpoint_ical_field_demo.py — the per-line parsing logic of the iCal reader,
# captured as pure Python and compiled to a Form recipe.
#
# Parsing a format is GRAMMAR work — the one thing this body is clearest is not
# carrier (household-membrane.form: calendar-port; the BMF grammar family).
# This is the first piece of the iCal parser to leave the Python if-tree and
# execute as Form: given one unfolded iCal line and a field name, return the
# field's value if the line carries that field, else "". The carrier still
# walks the lines (I/O) and keeps the VEVENT state, but the *decision* — does
# this line carry SUMMARY / DTSTART / LOCATION, and what is its value — runs
# on the kernel, with this Python as the value-identical fallback. The rest of
# the parser follows, line-walk next, recipe by recipe.
#
# A field line is  NAME[;params]:value  — so the name ends at the first ':'
# or ';', whichever comes first, and the value is everything after the ':'.
# Built only from str_len / substring / str_eq, so it mirrors the kernel ops.


def slen(s):
    return len(s)


def ch(s, i):                       # one character at i (kernel: substring s i i+1)
    return s[i:i + 1]


def find_ch(s, c, i):               # index of char c from i, or -1
    if i >= slen(s):
        return -1
    if str_eq(ch(s, i), c):
        return i
    return find_ch(s, c, i + 1)


def str_eq(a, b):
    return a == b


def field_end(line):                # name ends at first ':' or ';'
    colon = find_ch(line, ":", 0)
    semi = find_ch(line, ";", 0)
    if colon < 0:
        return -1
    if semi >= 0 and semi < colon:
        return semi
    return colon


def starts(line, name):             # does line's field-name == name
    e = field_end(line)
    if e < 0:
        return 0
    return 1 if str_eq(line[0:e], name) else 0


def ical_field(line, name):
    if starts(line, name) == 0:
        return ""
    colon = find_ch(line, ":", 0)
    if colon < 0:
        return ""
    return line[colon + 1:slen(line)]


line = "DTSTART;VALUE=DATE:20260615"
name = "DTSTART"
result = ical_field(line, name)     # -> "20260615"
