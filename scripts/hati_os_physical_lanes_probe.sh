#!/usr/bin/env bash
# Emit, compile, and run local Hati-OS native binaries against real host lanes.
#
# The harness is intentionally concrete:
#   Form recipes -> emitted C -> clang native binary -> local resource lane.
# The shell here orchestrates the proof and writes evidence; the lane data is
# carried by the emitted Hati driver/server binaries.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="${WORK:-$ROOT/.cache/hati-os-physical-lanes/$STAMP}"
MODEL="${MODEL:-llama3.2:3b}"
mkdir -p "$WORK"

need() {
  command -v "$1" >/dev/null || {
    echo "FAIL: missing '$1'" >&2
    exit 1
  }
}

need "$CLANG"
need /bin/sh
need /usr/bin/printf
need /usr/bin/curl
need /usr/bin/sqlite3
need /usr/sbin/screencapture
need /usr/bin/osascript
need /usr/bin/say
need /usr/bin/afplay
need /usr/bin/file
need /usr/bin/grep
need /usr/bin/find
need /usr/bin/awk
need /usr/bin/xmllint
need /usr/sbin/system_profiler
need /opt/homebrew/bin/ffmpeg
need /opt/homebrew/bin/rec
need /opt/homebrew/bin/soxi
need /opt/homebrew/bin/ollama

if [[ ! -x "$GO_BIN" ]]; then
  (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

append_json_lane() {
  local lane="$1" protocol="$2" command="$3" output_file="$4" artifact="$5" status="$6"
  local bytes preview
  bytes="$(wc -c < "$output_file" | tr -d ' ')"
  preview="$(LC_ALL=C head -c 1200 "$output_file" | tr '\0' ' ' | json_escape)"
  command="$(printf '%s' "$command" | json_escape)"
  artifact="$(printf '%s' "$artifact" | json_escape)"
  status="$(printf '%s' "$status" | json_escape)"
  cat >> "$WORK/lanes.jsonl" <<EOF
{"lane":"$lane","protocol":"$protocol","native_binary":"$WORK/fkdump","command":$command,"output_file":"$output_file","artifact":$artifact,"captured_bytes":$bytes,"status":$status,"stdout_preview":$preview}
EOF
}

emit_driver_binaries() {
  cat "$FORMDIR/form-stdlib/minimal-surface.fk" \
      "$FORMDIR/form-stdlib/hati-os-kernel.fk" \
      "$FORMDIR/form-stdlib/hati-os-kernel-emit.fk" \
      "$FORMDIR/form-stdlib/hati-os-match.fk" > "$WORK/physical-driver.fk"
  cat >> "$WORK/physical-driver.fk" <<'EOF'
(defn fkdump-loop (limit)
    (fk-if (fk-le (fk-arg) (fk-lit limit))
        (fk-if (fk-buf (fk-arg))
            (fkd-seq (fkd-putc (fk-buf (fk-arg)))
                     (fk-call 1 (fk-add (fk-arg) (fk-lit 1))))
            (fk-lit 0))
        (fk-lit 0)))
(defn fkdump-fns (limit)
    (list (fk-call 1 (fk-lit 0))
          (fkdump-loop limit)))

(print "==DUMP==")
(print (fkc-emit-driver (fkdump-fns 32767)))
(print "==COUNT==")
(print (fkc-emit-driver (fkcount-fns)))
(print "==MATCH_HOST==")
(print (fkc-emit-driver (fm-contains-fns "HATI_HOST_EXEC_OK")))
(print "==SERVER==")
(let resp (fkresp "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"lane\":\"kernel:route\",\"served_by\":\"Hati-OS-native-binary\",\"body\":\"PUTC response bytes from Form cells\"}"))
(print (fkc-emit-server (list resp)))
(print "==END==")
EOF
  (cd "$FORMDIR" && "$GO_BIN" "$WORK/physical-driver.fk" 2>/dev/null) > "$WORK/emit.out"
  sed -n '/^==DUMP==$/,/^==COUNT==$/p' "$WORK/emit.out" | sed -e '1d' -e '$d' > "$WORK/fkdump.c"
  sed -n '/^==COUNT==$/,/^==MATCH_HOST==$/p' "$WORK/emit.out" | sed -e '1d' -e '$d' > "$WORK/fkcount.c"
  sed -n '/^==MATCH_HOST==$/,/^==SERVER==$/p' "$WORK/emit.out" | sed -e '1d' -e '$d' > "$WORK/fkmatch-host.c"
  sed -n '/^==SERVER==$/,/^==END==$/p' "$WORK/emit.out" | sed -e '1d' -e '$d' > "$WORK/fkserver.c"
  "$CLANG" -O2 -o "$WORK/fkdump" "$WORK/fkdump.c"
  "$CLANG" -O2 -o "$WORK/fkcount" "$WORK/fkcount.c"
  "$CLANG" -O2 -o "$WORK/fkmatch-host" "$WORK/fkmatch-host.c"
  "$CLANG" -O2 -o "$WORK/fkserver" "$WORK/fkserver.c"
}

run_with_limit() {
  local seconds="$1"
  shift
  "$@" &
  local pid=$!
  local left="$seconds"
  while kill -0 "$pid" 2>/dev/null; do
    if [[ "$left" -le 0 ]]; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi
    sleep 1
    left=$((left - 1))
  done
  wait "$pid"
}

run_hati_dump() {
  local lane="$1" protocol="$2" command="$3" artifact="$4" seconds="${5:-20}"
  local out="$WORK/${lane//[^A-Za-z0-9_.-]/_}.out"
  set +e
  run_with_limit "$seconds" "$WORK/fkdump" /bin/sh -c "$command" > "$out" 2>&1
  local rc=$?
  set -e
  append_json_lane "$lane" "$protocol" "$command" "$out" "$artifact" "hati_driver_rc=$rc"
}

run_kernel_route() {
  local port=$((18000 + ($$ % 1000)))
  "$WORK/fkserver" "$port" > "$WORK/fkserver.log" 2>&1 &
  local server_pid=$!
  sleep 1
  local out="$WORK/kernel_route.out"
  set +e
  /usr/bin/curl -sS --max-time 5 "http://127.0.0.1:$port/" > "$out" 2>&1
  local rc=$?
  set -e
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  append_json_lane "kernel_route" "kernel:route" "$WORK/fkserver $port ; curl http://127.0.0.1:$port/" "$out" "$WORK/fkserver" "curl_rc=$rc"
}

emit_driver_binaries
: > "$WORK/lanes.jsonl"

run_hati_dump "host_exec" "host:exec" \
  '/usr/bin/printf "HATI_HOST_EXEC_OK physical command stdout from pid=$$ on $(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)\n"' \
  "" 10

"$WORK/fkmatch-host" /usr/bin/printf "HATI_HOST_EXEC_OK" > "$WORK/host_exec_match.out" 2>&1 || true
append_json_lane "host_exec_match" "stream:read" \
  "$WORK/fkmatch-host /usr/bin/printf HATI_HOST_EXEC_OK" "$WORK/host_exec_match.out" "$WORK/fkmatch-host" "match_binary"

run_hati_dump "http_request" "http:request" \
  '/usr/bin/curl -sS --max-time 8 https://api.coherencycoin.com/api/health ; /bin/echo "\nHATI_EXIT=$?"' \
  "" 15

run_kernel_route

run_hati_dump "store_query" "store:query" \
  "/usr/bin/sqlite3 '$WORK/lane.sqlite' 'drop table if exists lane; create table lane(kind text, value integer); insert into lane values (\"store\", 7),(\"store\", 8); select \"store_sum=\" || sum(value) from lane;' ; /bin/echo HATI_EXIT=\$?" \
  "$WORK/lane.sqlite" 10

run_hati_dump "shell_applets" "stream:read+host:file+store:query+kernel:call" \
  "cd '$WORK' && /usr/bin/printf 'alpha 1\nbeta 2\nalpha 3\n' > applets.txt && /usr/bin/grep beta applets.txt && /usr/bin/find . -maxdepth 1 -name applets.txt && /usr/bin/awk '{sum[\$1]+=\$2} END{for (k in sum) print k,sum[k]}' applets.txt && /bin/echo '<root><item>xmlpath</item></root>' > sample.xml && /usr/bin/xmllint --xpath 'string(/root/item)' sample.xml ; /bin/echo '\nHATI_EXIT='\$?" \
  "$WORK/applets.txt $WORK/sample.xml" 10

run_hati_dump "agent_model_qna" "kernel:call+host:exec" \
  "/bin/echo 'Respond exactly with HATI_AGENT_QA_OK' | /opt/homebrew/bin/ollama run '$MODEL' ; /bin/echo HATI_EXIT=\$?" \
  "ollama:$MODEL" 60

MIC_WAV="$WORK/mic_sample.wav"
run_hati_dump "audio_mic_sample" "host:exec+host:file" \
  "/opt/homebrew/bin/rec -q -r 16000 -c 1 -b 16 -e signed-integer '$MIC_WAV' trim 0 0.25 2>&1; rc=\$?; if [ -s '$MIC_WAV' ]; then /bin/echo mic_wav_bytes=\$(/usr/bin/wc -c < '$MIC_WAV'); /opt/homebrew/bin/soxi '$MIC_WAV'; fi; /bin/echo HATI_EXIT=\$rc" \
  "$MIC_WAV" 20

SAY_AIFF="$WORK/speaker_push.aiff"
run_hati_dump "audio_speaker_push" "host:exec+host:file" \
  "/usr/bin/say -o '$SAY_AIFF' 'Hati OS physical speaker lane' 2>&1; rc1=\$?; if [ -s '$SAY_AIFF' ]; then /usr/bin/afplay '$SAY_AIFF' >/dev/null 2>&1; rc2=\$?; /bin/echo speaker_aiff_bytes=\$(/usr/bin/wc -c < '$SAY_AIFF'); /usr/bin/file '$SAY_AIFF'; else rc2=99; fi; /bin/echo HATI_EXIT_SAY=\$rc1 HATI_EXIT_AFPLAY=\$rc2" \
  "$SAY_AIFF" 30

SCREEN_PNG="$WORK/screen_read.png"
run_hati_dump "screen_read_write" "host:exec+host:file" \
  "/usr/bin/osascript -e 'display notification \"Hati OS screen write lane\" with title \"Coherence\"' 2>&1; rc1=\$?; /usr/sbin/screencapture -x '$SCREEN_PNG' 2>&1; rc2=\$?; if [ -s '$SCREEN_PNG' ]; then /bin/echo screen_png_bytes=\$(/usr/bin/wc -c < '$SCREEN_PNG'); /usr/bin/file '$SCREEN_PNG'; fi; /bin/echo HATI_EXIT_NOTIFY=\$rc1 HATI_EXIT_CAPTURE=\$rc2" \
  "$SCREEN_PNG" 20

CAM_JPG="$WORK/camera_frame.jpg"
run_hati_dump "camera_frame" "host:exec+host:file" \
  "/opt/homebrew/bin/ffmpeg -hide_banner -loglevel error -f avfoundation -framerate 30 -video_size 640x480 -i '0:none' -frames:v 1 '$CAM_JPG' 2>&1; rc=\$?; if [ -s '$CAM_JPG' ]; then /bin/echo camera_jpg_bytes=\$(/usr/bin/wc -c < '$CAM_JPG'); /usr/bin/file '$CAM_JPG'; fi; /bin/echo HATI_EXIT=\$rc" \
  "$CAM_JPG" 20

run_hati_dump "sensor_inventory" "stream:read" \
  "/opt/homebrew/bin/ffmpeg -hide_banner -f avfoundation -list_devices true -i '' 2>&1 | /usr/bin/sed -n '1,20p'; /bin/echo '--- audio/display inventory ---'; /usr/sbin/system_profiler SPAudioDataType SPDisplaysDataType 2>/dev/null | /usr/bin/grep -E 'MacBook Pro Microphone|MacBook Pro Speakers|MacBook Pro Camera|Resolution|Display Type|Input Channels|Output Channels|Current SampleRate' | /usr/bin/sed -n '1,30p'; /bin/echo '--- gps/mobile sensor lane ---'; /bin/echo 'GPS_PROVIDER=not_exposed_on_this_mac_host'; /bin/echo HATI_EXIT=0" \
  "" 15

python3 - "$WORK" "$STAMP" "$MODEL" <<'PY'
import json
import pathlib
import sys

work = pathlib.Path(sys.argv[1])
stamp = sys.argv[2]
model = sys.argv[3]
lanes = [json.loads(line) for line in (work / "lanes.jsonl").read_text().splitlines() if line.strip()]
summary = {
    "generated_at": stamp,
    "work_dir": str(work),
    "chain": [
        "Form stdlib recipes",
        "form-kernel-go emits C",
        "clang compiles native Hati binaries",
        "Hati driver/server binaries touch local host resource lanes",
        "lane stdout/artifacts captured under work_dir",
    ],
    "native_binaries": {
        "fkdump": str(work / "fkdump"),
        "fkcount": str(work / "fkcount"),
        "fkmatch_host": str(work / "fkmatch-host"),
        "fkserver": str(work / "fkserver"),
    },
    "model": model,
    "lanes": lanes,
}
(work / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(work / "summary.json")
print(json.dumps({"lanes": len(lanes), "work_dir": str(work)}, sort_keys=True))
PY
