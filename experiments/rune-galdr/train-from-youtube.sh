#!/usr/bin/env bash
# train-from-youtube.sh — train each rune's vibration from REAL human galdr on public
# YouTube, instead of macOS `say`. For each Elder Futhark rune: search one galdr video,
# take a mid clip, measure its vocal-formant signature (sox), and emit the Form row for
# nordic-runes.fk — plus a SOURCES line crediting the video.
#
# Carrier-last: yt-dlp + sox are oracles/tools; the rune MODEL stays Form. The formant
# bands (250–4000 Hz) already reject most drum, so most galdr clips need no separation;
# heavily-drummed sources can be cleaned first with separate-galdr.sh.
#
#   train-from-youtube.sh            # 24 rows -> stdout ; SOURCES -> stderr ; cache -> ~/.coherence-network/recordings/yt-runes
set -uo pipefail
DIR="$HOME/.coherence-network/recordings/yt-runes"; mkdir -p "$DIR"
FB=(250 450  450 700  700 1100  1100 1700  1700 2600  2600 4000)
vb() { sox "$1" -n highpass 80 sinc "$2"-"$3" stat 2>&1 | awk '/RMS +amplitude/{printf "%d",$3*10000+0.5}'; }
shape() { local w="$1"
  local r=( $(vb "$w" "${FB[0]}" "${FB[1]}") $(vb "$w" "${FB[2]}" "${FB[3]}") $(vb "$w" "${FB[4]}" "${FB[5]}") \
            $(vb "$w" "${FB[6]}" "${FB[7]}") $(vb "$w" "${FB[8]}" "${FB[9]}") $(vb "$w" "${FB[10]}" "${FB[11]}") )
  local max=0 v; for v in "${r[@]}"; do [[ ${v:-0} -gt $max ]] && max=$v; done; [[ $max -eq 0 ]] && max=1
  local q=(); for v in "${r[@]}"; do q+=( $(( (${v:-0}*9+max/2)/max )) ); done; echo "${q[*]}"; }

# glyph | name | phoneme | aett | keyword | youtube search query
RUNES=(
"ᚠ|fehu|f|1|wealth|fehu rune galdr chant"          "ᚢ|uruz|u|1|strength|uruz rune galdr chant"
"ᚦ|thurisaz|th|1|thorn|thurisaz rune galdr chant"   "ᚨ|ansuz|a|1|breath-god|ansuz rune galdr chant"
"ᚱ|raidho|r|1|journey|raidho rune galdr chant"       "ᚲ|kenaz|k|1|torch|kenaz rune galdr chant"
"ᚷ|gebo|g|1|gift|gebo rune galdr chant"              "ᚹ|wunjo|w|1|joy|wunjo rune galdr chant"
"ᚺ|hagalaz|h|2|hail|hagalaz rune galdr chant"        "ᚾ|nauthiz|n|2|need|nauthiz rune galdr chant"
"ᛁ|isa|i|2|ice|isa rune galdr chant"                 "ᛃ|jera|y|2|harvest|jera rune galdr chant"
"ᛇ|eihwaz|ei|2|yew|eihwaz rune galdr chant"          "ᛈ|perthro|p|2|fate-lot|perthro rune galdr chant"
"ᛉ|algiz|z|2|protection|algiz rune galdr chant"      "ᛋ|sowilo|s|2|sun|sowilo rune galdr chant"
"ᛏ|tiwaz|t|3|justice|tiwaz rune galdr chant"         "ᛒ|berkano|b|3|birch-birth|berkano rune galdr chant"
"ᛖ|ehwaz|e|3|horse|ehwaz rune galdr chant"           "ᛗ|mannaz|m|3|human|mannaz rune galdr chant"
"ᛚ|laguz|l|3|water|laguz rune galdr chant"           "ᛜ|ingwaz|ng|3|seed|ingwaz rune galdr chant"
"ᛟ|othala|o|3|home-dna|othala rune galdr chant"      "ᛞ|dagaz|d|3|day-dawn|dagaz rune galdr chant"
)

echo "# rune | youtube-id | title  (real-galdr training sources)" >&2
for r in "${RUNES[@]}"; do
  IFS='|' read -r glyph name ph aett kw query <<<"$r"
  wav="$DIR/$name.16k.wav"
  if [[ ! -f "$wav" ]]; then
    yt-dlp --no-warnings --download-sections "*15-75" -x --audio-format wav -o "$DIR/$name.%(ext)s" "ytsearch1:$query" >/dev/null 2>&1 || true
    [[ -f "$DIR/$name.wav" ]] && sox "$DIR/$name.wav" -c 1 -r 16000 "$wav" 2>/dev/null
  fi
  vid=$(yt-dlp --no-warnings "ytsearch1:$query" --print "%(id)s|%(title).50s" --skip-download 2>/dev/null | head -1)
  if [[ -f "$wav" ]]; then
    dur=$(soxi -D "$wav" 2>/dev/null | cut -d. -f1); mid=$(( ${dur:-16} / 2 ))
    sox "$wav" "$DIR/$name.clip.wav" trim "$mid" 8 2>/dev/null
    sig="$(shape "$DIR/$name.clip.wav")"
    echo "        (rune \"$glyph\" \"$name\" \"$ph\" $aett \"$kw\" (list $sig))"
    echo "$name | $vid" >&2
  else
    echo "        (rune \"$glyph\" \"$name\" \"$ph\" $aett \"$kw\" (list 9 5 3 2 2 1))  ; download failed — synth fallback"
    echo "$name | DOWNLOAD-FAILED ($query)" >&2
  fi
done
