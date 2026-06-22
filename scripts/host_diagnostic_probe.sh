#!/usr/bin/env bash
# host_diagnostic_probe.sh — the THIN per-host carrier for the diagnostic lane.
#
# The decision logic lives in form/form-stdlib/host-diagnostic.fk (four-way + native, runs on every
# kernel and every metal). This carrier does ONLY physical I/O: measure which capabilities are present
# on THIS host, build the Form profile, and run the lane body to print the host's readiness and to
# ATTRIBUTE the known divergent bands (carrier absent here -> environmental; present -> real bug).
# One carrier per platform, each thin; this is the linux/container twin of host-sense-organ's mac carrier.
#
# "Even the hardware spec is a claim until measured" — so every status below is MEASURED, never assumed.
set -uo pipefail
cd "$(dirname "$0")/../form" || exit 1

# cap-ids must match host-diagnostic.fk's band convention: postgres=1 shell=2 gpu=3 net=4 fs=5
# status: 0 absent, 1 degraded, 2 present
probe_postgres() { command -v pg_isready >/dev/null 2>&1 && pg_isready -q 2>/dev/null && echo 2 || echo 0; }
probe_shell()    { [ -n "${SHELL:-}" ] || command -v sh >/dev/null 2>&1 && echo 2 || echo 0; }
probe_gpu()      { { command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; } && echo 2 || echo 0; }
probe_net()      { curl -sS --max-time 3 -o /dev/null https://api.coherencycoin.com/api/health 2>/dev/null && echo 2 || echo 0; }
probe_fs()       { t="$(mktemp 2>/dev/null)" && rm -f "$t" 2>/dev/null && echo 2 || echo 0; }

P=$(probe_postgres); S=$(probe_shell); G=$(probe_gpu); N=$(probe_net); F=$(probe_fs)
echo "measured profile (this host): postgres=$P shell=$S gpu=$G net=$N fs=$F"

# Build the Form profile + the known divergent bands with their inferred required carriers, then run
# the lane body. mesh-sensings-store needs postgres(1); the sh-* debug bands need a shell(2);
# form-bml-core-parity needs no external carrier (5=fs present) so a divergence there reads as REAL.
KERNEL="./form-kernel-go/bin-go"
DRIVER="$(mktemp /tmp/hd-driver.XXXXXX.fk)"
cat > "$DRIVER" <<EOF
(do
  (let profile (list (hd-probe 1 $P) (hd-probe 2 $S) (hd-probe 3 $G) (hd-probe 4 $N) (hd-probe 5 $F)))
  ; the 6 consolidation divergences, each (band-id required-cap):
  (let dlist (list (list 1 1)    ; mesh-sensings-store -> postgres
                   (list 2 2) (list 3 2) (list 4 2) (list 5 2)  ; sh-exec/live/parse/v2 -> shell
                   (list 6 5)))  ; form-bml-core-parity -> fs (no external carrier)
  (print (str_concat "host-readiness-ppm: " (int_to_str (hd-awakeness profile))))
  (print (str_concat "divergences-real:   " (int_to_str (hd-count-real profile dlist))))
  (print (str_concat "divergences-env:    " (int_to_str (hd-count-env profile dlist))))
  0)
EOF
"$KERNEL" form-stdlib/host-diagnostic.fk "$DRIVER" 2>&1 | grep -E "host-readiness|divergences"
rm -f "$DRIVER"
