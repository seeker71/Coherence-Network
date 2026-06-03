#!/bin/sh
# entrypoint.sh — launch the kernel-router (form-kernel-rust serve) as the
# request front door, resolving env at run time so PORT / UPSTREAM / ROUTES are
# container-configurable without rebuilding the image.
#
#   KERNEL_ROUTER_PORT  the port the router listens on   (default 8080)
#   KERNEL_ROUTER_HOST  the interface the router binds    (default 0.0.0.0)
#   UPSTREAM_URL        the CPython fan-out target        (default http://api:8000)
#   ROUTES_FILE         the routes manifest               (default /routes/shadow-routes.fk)
#   COH_ROUTER_COMPARE  COMPARE mode: 1/true -> every NATIVE route is shadow-
#                       compared against UPSTREAM_URL and CPython's (safe) response
#                       is returned (zero behavior change; X-Form-Compare +
#                       [compare] logs carry the verdict). Read by the binary from
#                       the process env directly — passed through, not a CLI flag.
#                       Unset -> native routes serve+return native (the cutover).
#                       See deploy/kernel-router/COMPARE_MODE.md.
#
# HOST binding: the kernel's `serve` defaults to 127.0.0.1 (loopback) — correct
# for a same-host proof harness, but UNREACHABLE across the container boundary
# (Docker's host port-forward and Traefik reach a container over its bridge IP,
# not its loopback). So in-container the entrypoint binds 0.0.0.0 by default; the
# localhost-only exposure of a shadow run is provided at the HOST level by
# `docker run -p 127.0.0.1:<port>:8080`, not by the in-container bind address.
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
HOST="${KERNEL_ROUTER_HOST:-0.0.0.0}"
UPSTREAM="${UPSTREAM_URL:-http://api:8000}"
ROUTES="${ROUTES_FILE:-/routes/shadow-routes.fk}"

set -- serve --host "$HOST" --port "$PORT" --routes "$ROUTES" --upstream "$UPSTREAM"

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

# COMPARE mode is read by the binary directly from the process env (not a CLI
# flag), so it is already in scope for the exec below. Surface its state in the
# launch line so an operator reading container logs knows the posture.
COMPARE="${COH_ROUTER_COMPARE:-}"
case "$(printf '%s' "$COMPARE" | tr '[:upper:]' '[:lower:]')" in
  1|true) COMPARE_NOTE=" [COMPARE on: native routes shadow-compared vs $UPSTREAM, CPython returned]" ;;
  *)      COMPARE_NOTE="" ;;
esac

echo "kernel-router: serve --host $HOST --port $PORT --routes $ROUTES --upstream $UPSTREAM (shadow mode: empty routes -> all fan-out)$COMPARE_NOTE"
exec /app/bin/form-kernel-rust "$@"
