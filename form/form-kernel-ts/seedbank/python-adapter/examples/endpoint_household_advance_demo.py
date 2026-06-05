# endpoint_household_advance_demo.py — the Hati Suci request lifecycle,
# captured as pure Python and compiled to a Form recipe.
#
# The household board's state machine: a request moves
#   open → acknowledged → in_progress → completed,  or is  cancelled.
# Each move is a (status, verb) pair; `advance` returns the next status
# code, or -1 for an illegal move. The live lifecycle endpoints in
# api/app/routers/household.py compute their next status by running THIS
# recipe on the kernel (serve_via_kernel), with the value-identical
# Python below as the fallback. FastAPI stays the HTTP doorway; the
# membrane's lifecycle is a Form recipe — the first household rule to
# leave the Python if-tree and execute as Form.
#
# Encoding — numbers are the substrate's native tongue:
#   status:  open=0  acknowledged=1  in_progress=2  completed=3  cancelled=4
#   verb:    acknowledge=0  start=1  complete=2  cancel=3
# "active" (a request still in motion) is simply status < 3.
#
# Three runtimes produce identical results: CPython, TS evalPython, Rust.


def advance(status, verb):
    if verb == 0:                       # acknowledge: only an open request
        return 1 if status == 0 else -1
    if verb == 1:                       # start: from open or acknowledged
        return 2 if status < 2 else -1
    if verb == 2:                       # complete: any active request
        return 3 if status < 3 else -1
    if verb == 3:                       # cancel: any active request
        return 4 if status < 3 else -1
    return -1


status = 0
verb = 0
result = advance(status, verb)
