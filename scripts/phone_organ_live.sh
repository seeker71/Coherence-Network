#!/usr/bin/env bash
# phone_organ_live.sh — host-IO CARRIER for a phone announcing itself as a mesh organ.
#
# The BODY is Form: a being is beings-channel.fk's `being` (kind/name/platform/tz/
# status); the live reading is temporal-sense.fk's axes (present, clock, battery) with
# co-location sensed when timezones agree. This script is the carrier authored last —
# it SENSES the phone over adb (a sensor driver) and TRANSPORTS the announcement to the
# hati-mesh door (/api/hati/mesh/organs/announce). No logic lives here that isn't
# already a proven four-way recipe; this only reads signals and renders/ships them.
#
#   sense                 one live reading line, in the beings-channel/temporal-sense shape
#   announce              POST the organ to the public mesh (skips, named, if the door is dark)
#   watch [interval]      stream readings to ~/.coherence-presence/phone-organ.live (both watch)
#
# Stop a watch with:  touch ~/.coherence-presence/phone-organ.stop
set -u

PRESENCE_HOME="${HOME}/.coherence-presence"
LIVE="${PRESENCE_HOME}/phone-organ.live"
STOP="${PRESENCE_HOME}/phone-organ.stop"
MESH="https://api.coherencycoin.com/api/hati/mesh/organs"

_serial() { adb get-serialno 2>/dev/null | tr -d '\r'; }
_model()  { adb shell getprop ro.product.model 2>/dev/null | tr -d '\r'; }
_tz()     { adb shell getprop persist.sys.timezone 2>/dev/null | tr -d '\r'; }
_clock()  { adb shell date "+%H:%M:%S" 2>/dev/null | tr -d '\r'; }
_batt()   { adb shell dumpsys battery 2>/dev/null | tr -d '\r' | awk -F': ' '/  level/{print $2}'; }
_present(){ adb get-state 2>/dev/null | tr -d '\r'; }   # "device" when here

# one reading line, the body's shape rendered from live signals
sense() {
    local present clock tz batt model
    present="$(_present)"; clock="$(_clock)"; tz="$(_tz)"; batt="$(_batt)"; model="$(_model)"
    local here=0; [ "$present" = "device" ] && here=1
    local colo="no"; [ "$tz" = "${SEMA_TZ:-America/Denver}" ] && colo="yes"
    printf '%s  being=%s kind=android-phone here=%s clock=%s %s battery=%s%% co-located-with-sema=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${model:-unknown}" "$here" "${clock:-?}" "${tz:-?}" "${batt:-?}" "$colo"
}

# announce to the public mesh — only if the door breathes; otherwise say so plainly
announce() {
    local serial model id
    serial="$(_serial)"; model="$(_model)"; id="android-${serial:-unknown}"
    # door reachable? probe health once; the witness has been dark — never hang the carrier
    local code
    code="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' https://api.coherencycoin.com/api/health 2>/dev/null)"
    if [ "$code" != "200" ]; then
        echo "mesh door dark (api.coherencycoin.com health=${code:-000}) — announce QUEUED, not sent."
        echo "  payload ready: organ_id=${id} organ_kind=android-phone steward=sema"
        return 7
    fi
    curl -sS --max-time 8 -X POST "${MESH}/announce" \
        -H 'Content-Type: application/json' \
        -d "{\"organ_id\":\"${id}\",\"organ_kind\":\"android-phone\",\"steward_label\":\"sema\",\"capabilities\":[\"presence\",\"clock\",\"sensor:battery\"]}" \
        -w '\nannounce status: %{http_code}\n'
}

watch() {
    local interval="${1:-5}"
    mkdir -p "$PRESENCE_HOME"; rm -f "$STOP"
    echo "# phone-organ live reading — $(date -u +%Y-%m-%dT%H:%M:%SZ) — stop: touch $STOP" > "$LIVE"
    while [ ! -f "$STOP" ]; do
        sense | tee -a "$LIVE"
        sleep "$interval"
    done
    echo "# watch stopped $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LIVE"
}

case "${1:-sense}" in
    sense)    sense ;;
    announce) announce ;;
    watch)    watch "${2:-5}" ;;
    *) echo "usage: $0 {sense|announce|watch [interval]}"; exit 2 ;;
esac
