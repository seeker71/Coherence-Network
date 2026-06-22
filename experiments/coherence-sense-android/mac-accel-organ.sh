#!/usr/bin/env bash
# mac-accel-organ.sh — read RESPIRATORY RATE from the phone's motion, via ADB, in Form.
#
# Breathing is chest MOTION, not sound — a mic can't hear calm breathing but an accelerometer feels it.
# The phone under the pillow / on the mattress is the motion sense organ; this carrier polls its
# linear_acceleration ring buffer over ADB (the Coherence Sense app keeps the sensor active at ~5Hz,
# gravity already removed = pure dynamic motion), dedups by device timestamp into a CSV, and reads the
# breathing rate with the four-way-proven breath-rhythm.fk recipe (autocorrelation finds the period).
#
# WHY THIS WORKS WHERE THE MIC DIDN'T: the rate lives in the slow back-and-forth of the chest. A signed
# motion axis oscillates ONCE per breath, so its autocorrelation peak IS the breath interval. (Motion
# ENERGY x²+y²+z² would double the frequency — so we feed the SIGNED dominant-variance axis, not energy.)
#
# NEEDS: an ADB-connected phone (USB or `adb tcpip` over wifi) running Coherence Sense (keeps the sensor
# alive). Local only — the motion CSV never leaves this Mac.
#
# Run:  mac-accel-organ.sh --log [DIR]         poll linear_acceleration until SLEEP_STOP_HOUR -> DIR/accel.csv
#       mac-accel-organ.sh --breathing [DIR]   read accel.csv -> respiratory rate per block + night median
#       mac-accel-organ.sh --probe             10s live check that motion is being captured
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FORM="${SLEEP_FORM:-$ROOT/form}"
DATE="${SLEEP_DATE:-$(date +%Y-%m-%d)}"
DIR="${ACCEL_DIR:-$HOME/sleep-$DATE}"
CSV="$DIR/accel.csv"
KERNEL="${SLEEP_KERNEL:-$DIR/kernel-go}"
[[ -x "$KERNEL" ]] || KERNEL="$FORM/form-kernel-go/bin-go"
POLL="${ACCEL_POLL:-7}"            # seconds between polls (buffer holds ~10s at 5Hz)
STOP_HOUR="${SLEEP_STOP_HOUR:-8}"
BLOCK_S="${ACCEL_BLOCK_S:-300}"    # analysis block = 5 min
# breathing band at 5Hz: lag 10..30 samples = 2..6s = 30..10 breaths/min; spm = 5*60 = 300
BLO=10; BHI=30; SPM=300; CONF_FLOOR="${ACCEL_CONF_FLOOR:-25}"

mkdir -p "$DIR"

# pull the phone's linear_acceleration recent events: device-ts,x,y,z (one row per sample)
poll_accel() {
    adb shell "dumpsys sensorservice | awk '/^linear_acceleration: last/{f=1;next} f&&/ts=/{print} f&&/^[A-Za-z]/{exit}'" 2>/dev/null \
        | sed -E 's/.*ts=([0-9.]+), wall=([0-9: .-]+)\) *([-0-9.]+), *([-0-9.]+), *([-0-9.]+).*/\1,\2,\3,\4,\5/'
}

# br-rate over one block of signed dominant-axis samples (passed as a space list of scaled ints)
rate_of_block() {  # $1 = space-separated scaled-int axis samples -> "rate conf lag"
    local drv; drv="$(mktemp /tmp/accelbr-XXXXXX.fk)"
    printf '(do (let xs (list %s)) (print (br-rate xs %d %d %d)) (print (br-confidence xs %d %d)) (print (br-peak-lag xs %d %d)))\n' \
        "$1" "$BLO" "$BHI" "$SPM" "$BLO" "$BHI" "$BLO" "$BHI" > "$drv"
    local o; o="$( "$KERNEL" "$FORM/form-stdlib/breath-rhythm.fk" "$drv" 2>/dev/null )"; rm -f "$drv"
    echo "$(sed -n 1p <<<"$o") $(sed -n 2p <<<"$o") $(sed -n 3p <<<"$o")"
}

if [[ "${1:-}" == "--probe" ]]; then
    echo "[accel] 10s live capture probe (move the phone to see motion)..."
    : > /tmp/accel_probe.csv
    for p in 1 2; do poll_accel >> /tmp/accel_probe.csv; sleep 5; done
    sort -u -t, -k1,1 /tmp/accel_probe.csv > /tmp/accel_probe_d.csv
    awk -F, 'NR==1{f=$1}{l=$1;n++; for(j=3;j<=5;j++){s[j]+=$j; ss[j]+=$j*$j}}
      END{ printf "  samples=%d span=%.1fs rate=%.1f Hz\n",n,l-f,(l>f?n/(l-f):0)
           for(j=3;j<=5;j++){m=s[j]/n; sd=sqrt(ss[j]/n-m*m); printf "  axis %d: mean=%.3f sd=%.4f\n",j-2,m,sd} }' /tmp/accel_probe_d.csv
    echo "  (still phone: sd ~0; under a breathing body: one axis sd rises and carries the rhythm)"
    exit 0
fi

if [[ "${1:-}" == "--breathing" ]]; then
    bdir="${2:-$DIR}"; bcsv="$bdir/accel.csv"
    [[ -f "$bcsv" ]] || { echo "no accel.csv in $bdir — run --log first"; exit 1; }
    # choose the dominant-variance axis across the whole night (the breathing-motion axis)
    AX=$(awk -F, 'NR>1{for(j=3;j<=5;j++){s[j]+=$j;ss[j]+=$j*$j};n++}
      END{best=0;bi=3; for(j=3;j<=5;j++){v=ss[j]/n-(s[j]/n)^2; if(v>best){best=v;bi=j}}; print bi}' "$bcsv")
    echo "Respiratory rhythm from phone motion — night of $DATE  (axis $((AX-2)) = strongest breathing motion)"
    echo "================================================================================"
    # per-block rate over the night, bucketed by wall-clock block
    rates=""; printf "  %-8s %-6s %-5s\n" "time" "br/min" "conf"
    for blk in $(awk -F, -v b="$BLOCK_S" 'NR>1{ split($2,w," "); split(w[2],t,":"); sec=t[1]*3600+t[2]*60+t[3]; print int(sec/b) }' "$bcsv" | sort -un); do
        series=$(awk -F, -v b="$BLOCK_S" -v blk="$blk" -v ax="$AX" 'NR>1{ split($2,w," "); split(w[2],t,":"); sec=t[1]*3600+t[2]*60+t[3]; if(int(sec/b)==blk) printf "%d ", int(1000*$ax) }' "$bcsv")
        cnt=$(wc -w <<<"$series"); [[ "$cnt" -lt 200 ]] && continue   # need ~40s of samples
        read -r rate conf lag < <(rate_of_block "$series")
        hh=$(awk -v blk="$blk" -v b="$BLOCK_S" 'BEGIN{s=blk*b; printf "%02d:%02d",int(s/3600),int((s%3600)/60)}')
        flag=""; [[ "${conf:-0}" -ge "$CONF_FLOOR" && "${rate:-0}" -ge 6 && "${rate:-0}" -le 40 ]] && { flag="  <-"; rates="$rates ${rate}"; }
        printf "  %-8s %-6s %-5s%s\n" "$hh" "${rate:-0}" "${conf:-0}" "$flag"
    done
    echo "--------------------------------------------------------------------------------"
    if [[ -n "$rates" ]]; then
        med=$(tr ' ' '\n' <<<"$rates" | grep -E '^[0-9]+$' | sort -n | awk '{a[NR]=$1} END{print a[int(NR/2)+1]}')
        echo "  Median respiratory rate over trusted blocks (<- marked): ~${med} breaths/min"
        echo "  Trusted blocks: $(wc -w <<<"$rates") of the night."
    else
        echo "  No block cleared the confidence floor ($CONF_FLOOR). Either the phone wasn't under a"
        echo "  breathing body, motion was too small, or the sensor wasn't sampling. Check --probe placement."
    fi
    echo "  (recipe: breath-rhythm.fk, four-way proven; signal: phone linear_acceleration via ADB; on-device only)"
    exit 0
fi

# default / --log : overnight capture
[[ "${1:-}" == "--log" ]] || true
adb get-state >/dev/null 2>&1 || { echo "[accel] FAIL no ADB device. Connect phone (USB or 'adb tcpip 5555' + 'adb connect <ip>') and run Coherence Sense."; exit 1; }
STOP_EPOCH="$(date -v"${STOP_HOUR}"H -v0M -v0S +%s)"; [[ "$STOP_EPOCH" -le "$(date +%s)" ]] && STOP_EPOCH=$(( STOP_EPOCH + 86400 ))
[[ -f "$CSV" ]] || echo "device_ts,wall,x,y,z" > "$CSV"
last_ts="$(awk -F, 'END{print $1+0}' "$CSV")"
echo "[accel] logging phone linear_acceleration -> $CSV  (poll ${POLL}s, stop $(date -r "$STOP_EPOCH" '+%H:%M'))"
while [[ "$(date +%s)" -lt "$STOP_EPOCH" ]]; do
    [[ -f "$DIR/STOP" ]] && { echo "[accel] STOP sentinel"; break; }
    poll_accel | awk -F, -v lt="$last_ts" '$1+0>lt' | sort -t, -k1,1n > /tmp/accel_new.$$ 2>/dev/null
    if [[ -s /tmp/accel_new.$$ ]]; then
        cat /tmp/accel_new.$$ >> "$CSV"
        last_ts="$(awk -F, 'END{print $1+0}' /tmp/accel_new.$$)"
    fi
    rm -f /tmp/accel_new.$$
    sleep "$POLL"
done
echo "[accel] capture done — $(tail -n +2 "$CSV" | wc -l | tr -d ' ') samples. Read it with: $0 --breathing $DIR"
