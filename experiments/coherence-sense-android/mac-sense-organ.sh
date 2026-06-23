#!/usr/bin/env bash
# mac-sense-organ.sh — thin host carrier; the BODY is form-stdlib/host-sense-organ.fk.
#
# The phone (MainActivity.kt) self-registers as android-phone; this is the macOS twin.
# This script does ONLY physical I/O: read the Mac's senses with sysctl/vm_stat/ioreg/
# pmset/netstat, ask the Form kernel which organs are active and what the mesh metrics
# are (host-sense-organ.fk — proven four-way), then POST to the cloud Hati mesh and write
# a local receipt. No decision lives here; every one is the Form recipe's.
#
# Privacy floor: vitals + availability only — no media is captured here (the mic stream
# is mac-speech-organ.sh's job). Run:  mac-sense-organ.sh   (loops; Ctrl-C to stop)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FORM="$ROOT/form"
MESH="${HATI_MESH:-https://api.coherencycoin.com/api}"
INTERVAL="${HATI_INTERVAL:-5}"
UA="coherence-sense-mac/0.2"
HATI="$HOME/.coherence-network/hati"; mkdir -p "$HATI"
RECEIPT="$HATI/mac-sense-latest.json"

# --- stable organ identity ---
if [[ -f "$HATI/macos-organ-id" ]]; then ORGAN_ID="$(cat "$HATI/macos-organ-id")"
else ORGAN_ID="hati-organ-macos-$(uuidgen | tr 'A-Z' 'a-z' | tr -d - | cut -c1-24)"; echo "$ORGAN_ID" > "$HATI/macos-organ-id"; fi
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"

# --- the Form body's kernel (built by form/validate.sh) ---
KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
if [[ ! -x "$KERNEL" ]]; then
    KERNEL="$(ls -t "$HOME"/.claude-worktrees/*/form/form-kernel-rust/target/release/form-kernel-rust 2>/dev/null | head -1 || true)"
fi
[[ -x "$KERNEL" ]] || { echo "FAIL no Form kernel — run: (cd $FORM && ./validate.sh form-stdlib/core.fk form-stdlib/host-sense-organ.fk form-stdlib/tests/host-sense-organ-band.fk)"; exit 1; }
FORMCLI="$FORM/form-cli"
if [[ ! -x "$FORMCLI" && -x "$FORM/.cache/form-cli-native-host" ]]; then
    FORMCLI="$FORM/.cache/form-cli-native-host"
fi
if [[ ! -x "$FORMCLI" && -x "$FORM/build-form-cli.sh" ]]; then
    (cd "$FORM" && ./build-form-cli.sh form-cli >/dev/null 2>&1) || true
    FORMCLI="$FORM/form-cli"
fi

# Run one Form driver against host-sense-organ.fk; echo its printed lines.
form_decide() {  # $1 = body expressions producing prints
    local drv; drv="$(mktemp /tmp/hso-XXXXXX.fk)"; printf '%s\n' "$1" > "$drv"
    ( cd "$FORM" && "$KERNEL" form-stdlib/host-sense-organ.fk "$drv" 2>/dev/null )
    rm -f "$drv"
}

native_host_row() {  # mic camera screen speech_gate freq surprises samples
    [[ -x "$FORMCLI" ]] || { echo ""; return; }
    printf 'native-host macos %s %s %s %s %s %s %s\nquit\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" \
        | "$FORMCLI" 2>/dev/null | head -1
}

# --- raw host readings (carrier measurement only) ---
ncpu="$(sysctl -n hw.ncpu)"
memsize="$(sysctl -n hw.memsize)"
pagesize="$(vm_stat | sed -n '1s/.*page size of \([0-9]*\) bytes.*/\1/p')"; pagesize="${pagesize:-4096}"
prev_rx=""; prev_tx=""; prev_t=""
announced=0; tick=0

read_net() {  # echo "rx tx" total bytes across non-loopback interfaces
    netstat -ib | awk 'NR>1 && $1!~/^lo/ && !seen[$1]++ {rx+=$7; tx+=$10} END {print rx, tx}'
}

while true; do
    now="$(date +%s)"
    # cpu: 1-min load over cores → ppm
    load1="$(sysctl -n vm.loadavg | awk '{print $2}')"
    cpu_ppm="$(awk -v l="$load1" -v n="$ncpu" 'BEGIN{p=l/n; if(p>1)p=1; printf "%d", p*1000000}')"
    # ram: (active+wired+compressed) pages → ppm of memsize
    eval "$(vm_stat | awk -F: '
        /Pages active/{gsub(/[ .]/,"",$2); print "a="$2}
        /Pages wired down/{gsub(/[ .]/,"",$2); print "w="$2}
        /Pages occupied by compressor/{gsub(/[ .]/,"",$2); print "c="$2}')"
    ram_ppm="$(awk -v a="${a:-0}" -v w="${w:-0}" -v c="${c:-0}" -v ps="$pagesize" -v m="$memsize" 'BEGIN{u=(a+w+c)*ps; p=u/m; if(p>1)p=1; printf "%d", p*1000000}')"
    # disk: data-volume usage → ppm (the system volume / reads tiny)
    disk_ppm="$(df -k /System/Volumes/Data 2>/dev/null | awk 'NR==2{printf "%d", ($3/($3+$4))*1000000}')"
    [[ -z "$disk_ppm" || "$disk_ppm" == "0" ]] && disk_ppm="$(df -k / | awk 'NR==2{printf "%d", ($3/($3+$4))*1000000}')"
    # net rates: delta bytes / dt
    read -r rx tx < <(read_net)
    if [[ -n "$prev_rx" && -n "$prev_t" ]]; then
        dt=$(( now - prev_t )); [[ $dt -lt 1 ]] && dt=1
        rx_bps=$(( (rx - prev_rx) / dt )); tx_bps=$(( (tx - prev_tx) / dt ))
        [[ $rx_bps -lt 0 ]] && rx_bps=0; [[ $tx_bps -lt 0 ]] && tx_bps=0
    else rx_bps=0; tx_bps=0; fi
    prev_rx="$rx"; prev_tx="$tx"; prev_t="$now"
    # gpu utilization (no sudo; absent on Apple Silicon → 0)
    gpu_ppm="$(ioreg -r -d 1 -c IOAccelerator 2>/dev/null | sed -n 's/.*"Device Utilization %"=\([0-9]*\).*/\1/p' | head -1)"
    gpu_ppm="$(( ${gpu_ppm:-0} * 10000 ))"
    # battery %
    batt="$(pmset -g batt 2>/dev/null | sed -n 's/.*[^0-9]\([0-9][0-9]*\)%.*/\1/p' | head -1)"; batt_ppm="$(( ${batt:-0} * 10000 ))"
    # sense availability flags (device/tool present = lane offerable; actual capture is per-organ)
    mic_ok=1; cam_ok=0; screen_ok=0
    command -v screencapture >/dev/null 2>&1 && screen_ok=1
    system_profiler SPCameraDataType 2>/dev/null | grep -q "Model" && cam_ok=1

    # --- the Form body decides (one kernel call) ---
    D=()
    while IFS= read -r line; do D+=("$line"); done < <(form_decide "(do
        (print (hso-organs-active $mic_ok $cam_ok $screen_ok))
        (print (hso-power-cost $cpu_ppm $gpu_ppm))
        (print (hso-signal $rx_bps $tx_bps))
        (print (hso-organ-count $mic_ok $cam_ok $screen_ok)))")
    organs="${D[0]:-[]}"; power="${D[1]:-0}"; signal="${D[2]:-0}"; ocount="${D[3]:-0}"
    lanes_json="$(printf '%s' "$organs" | sed 's/^\[//; s/\]$//' | tr ',' '\n' | sed 's/^ *//; s/ *$//' | grep -v '^$' | jq -R . | jq -s -c .)"
    [[ -z "$lanes_json" ]] && lanes_json='[]'
    native_row="$(native_host_row "$mic_ok" "$cam_ok" "$screen_ok" 0 0 0 "$tick")"
    native_json="$(jq -Rn --arg raw "$native_row" '$raw')"

    # --- POST to mesh (carrier marshalling) ---
    base="{\"organ_id\":\"$ORGAN_ID\",\"trust_score_ppm\":820000,\"signal_strength_ppm\":$signal,\"battery_level_ppm\":$batt_ppm,\"power_cost_ppm\":$power,\"discovery_state\":\"streaming\""
    if [[ $announced -eq 0 || $(( tick % 12 )) -eq 0 ]]; then
        curl -s -m 8 -X POST "$MESH/hati/mesh/organs/announce" -H "Content-Type: application/json" -H "User-Agent: $UA" \
            -d "$base,\"organ_kind\":\"host-kernel\",\"app\":\"coherence-sense-mac\",\"app_version\":\"0.2\",\"target\":\"macos-arm64\",\"display_name\":\"$HOST\",\"capabilities\":[\"cap.host.vitals\",\"cap.compute.cpu\",\"cap.compute.gpu\",\"cap.sensor.read\",\"cap.network.presence\",\"cap.mesh.presence\"],\"lanes\":$lanes_json}" >/dev/null && announced=1
    fi
    curl -s -m 8 -X POST "$MESH/hati/mesh/organs/heartbeat" -H "Content-Type: application/json" -H "User-Agent: $UA" \
        -d "$base,\"listening\":true,\"active_channels\":$lanes_json,\"native_host_instance_raw\":$native_json,\"sample_rate_hz\":1.0,\"bytes_per_second\":$(( rx_bps + tx_bps ))}" >/dev/null

    # --- local receipt (carrier write; the body's organs/metrics) ---
    jq -n --arg oid "$ORGAN_ID" --arg host "$HOST" --arg native_host "$native_row" --argjson lanes "$lanes_json" \
        --argjson cpu "$cpu_ppm" --argjson ram "$ram_ppm" --argjson disk "$disk_ppm" \
        --argjson gpu "$gpu_ppm" --argjson power "$power" --argjson signal "$signal" \
        --argjson batt "$batt_ppm" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '{organ_id:$oid,organ_kind:"host-kernel",target:"macos-arm64",host:$host,ts:$ts,
          organs_active:$lanes,cpu_load_ppm:$cpu,ram_used_ppm:$ram,disk_used_ppm:$disk,
          gpu_util_ppm:$gpu,power_cost_ppm:$power,signal_strength_ppm:$signal,battery_ppm:$batt,
          native_host_instance_raw:$native_host,
          privacy:"vitals-and-availability-only",body:"form-stdlib/host-sense-organ.fk"}' > "$RECEIPT"

    if [[ $(( tick % 6 )) -eq 0 ]]; then
        echo "[mac-sense] tick=$tick cpu=$((cpu_ppm/10000))% ram=$((ram_ppm/10000))% disk=$((disk_ppm/10000))% net=${rx_bps}/${tx_bps}B/s organs=$ocount lanes=$organs"
    fi
    tick=$(( tick + 1 ))
    [[ "${1:-}" == "--once" ]] && exit 0
    sleep "$INTERVAL"
done
