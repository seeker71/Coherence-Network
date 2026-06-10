# endpoint_lattice_stats_demo.py — substrate /api/substrate/lattice/stats
# transmuted through the kernel.
#
# The Python shape of lattice_stats(session): returns a flat dict with
# three integer counts. This demo shapes the same computation as a
# recipe the kernel can walk — build the dict, address it by key,
# return the total.
#
# Runs identically through:
#   python3 endpoint_lattice_stats_demo.py            - CPython
#   kernel-bmf-run <file.py>                   - Form-native walker
#   form-kernel-rust endpoint_lattice_stats_demo.fk   - native kernel
#
# The fetch + JSON-parse primitives (http_get, _json_to_dict) live on
# the kernel side; this demo holds the post-parse dict shape so the
# three-way parity gate stays on Python-level constructs. The real
# end-to-end transmutation proof — kernel binary against a live
# substrate response — lives in api/tests/test_substrate_kernel_parity.py.

# A canned lattice/stats response shape — the same field names the live
# endpoint returns. Used so the parity gate compares a deterministic
# value across all three runtimes without needing a substrate server.
stats = {"blueprints_total": 128, "recipes_total": 642, "cells_total": 319}

blueprints = stats["blueprints_total"]
recipes = stats["recipes_total"]
cells = stats["cells_total"]

# The transmuted-endpoint result: total of all three substrate counts.
# A Python lattice_stats caller would compose the same arithmetic on
# the same dict — this demo confirms the kernel walks the same recipe
# tree and reaches the same total.
blueprints + recipes + cells
