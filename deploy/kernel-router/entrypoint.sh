#!/bin/sh
# entrypoint.sh — launch the kernel-router (form-kernel-rust serve) as the
# request front door, resolving env at run time so PORT / UPSTREAM / ROUTES are
# container-configurable without rebuilding the image.
#
#   KERNEL_ROUTER_PORT  the port the router listens on   (default 8080)
#   UPSTREAM_URL        the CPython fan-out target        (default http://api:8000)
#   ROUTES_FILE         the routes manifest               (default /routes/shadow-routes.fk)
#
# In shadow mode the manifest binds an empty routes list, so the router serves
# zero native routes and fans EVERYTHING out to UPSTREAM_URL — byte-identical to
# hitting the upstream directly, with X-Form-Router: fanout-python on every
# response as live evidence.
#
# A raw S-expression manifest (the shadow default) needs no --stdlib. A
# BML-authored manifest (one that opens a `section [...]` block) is source-
# compiled at load and DOES need --stdlib; set STDLIB_DIR to enable it.
set -eu

PORT="${KERNEL_ROUTER_PORT:-8080}"
UPSTREAM="${UPSTREAM_URL:-http://api:8000}"
ROUTES="${ROUTES_FILE:-/routes/shadow-routes.fk}"

set -- serve --port "$PORT" --routes "$ROUTES" --upstream "$UPSTREAM"

# Optional: a BML manifest needs the source-compiler. Pass --stdlib only when
# STDLIB_DIR is set, so the raw-S-expression shadow default stays untouched.
if [ -n "${STDLIB_DIR:-}" ]; then
  set -- "$@" --stdlib "$STDLIB_DIR"
fi

# Optional: size the worker pool (default: host parallelism). Exposed so a
# deployment can tune it without a code change.
if [ -n "${KERNEL_ROUTER_WORKERS:-}" ]; then
  set -- "$@" --workers "$KERNEL_ROUTER_WORKERS"
fi

echo "kernel-router: serve --port $PORT --routes $ROUTES --upstream $UPSTREAM (shadow mode: empty routes -> all fan-out)"
exec /app/bin/form-kernel-rust "$@"
