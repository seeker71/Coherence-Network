#!/usr/bin/env bash
# voiceprint.sh — measure a voiceprint from a wav (sourced by enroll/identify carriers).
# A voiceprint = pitch bucket (median fundamental) + 6-band formant SHAPE (vocal-tract timbre).
# Carrier DSP only (sox); the speaker MATCH lives in form-stdlib/speaker-id.fk.
FB=(250 450  450 700  700 1100  1100 1700  1700 2600  2600 4000)
_vb() { sox "$1" -n highpass 80 sinc "$2"-"$3" stat 2>&1 | awk '/RMS +amplitude/{printf "%d",$3*10000+0.5}'; }
# pitch bucket: lowpass 350 strips harmonics so rough-frequency tracks f0; bucket /25.
_pitch_bucket() { local f; f="$(sox "$1" -n lowpass 350 stat 2>&1 | awk '/Rough +frequency/{print $3}')"; echo $(( (${f:-0}+12)/25 )); }
# echo "pitch f0 f1 f2 f3 f4 f5"  (7 ints)
voiceprint() {
  local w="$1"
  local r=( $(_vb "$w" "${FB[0]}" "${FB[1]}") $(_vb "$w" "${FB[2]}" "${FB[3]}") $(_vb "$w" "${FB[4]}" "${FB[5]}") \
            $(_vb "$w" "${FB[6]}" "${FB[7]}") $(_vb "$w" "${FB[8]}" "${FB[9]}") $(_vb "$w" "${FB[10]}" "${FB[11]}") )
  local max=0 v; for v in "${r[@]}"; do [[ ${v:-0} -gt $max ]] && max=$v; done; [[ $max -eq 0 ]] && max=1
  local q=(); for v in "${r[@]}"; do q+=( $(( (${v:-0}*9+max/2)/max )) ); done
  echo "$(_pitch_bucket "$w") ${q[*]}"
}
