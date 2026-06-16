#!/usr/bin/env bash
# form_codesign_conviction_demo.sh — byte-conviction for the Form code-signer.
#
# The gate that licenses dropping `ld` from the dylib path: the Form recipe
# form-codesign (co-sign) must produce the EXACT bytes `ld` produces for the
# same input. We build a real signed dylib, hand its [0:codeLimit] image and
# `ld`'s own signing parameters to co-sign, and diff the result against `ld`'s
# embedded signature. Byte-identity opens the gate — same shape as
# form_asm_conviction_demo.sh (Form asm bytes == clang bytes).
#
# Form bytes == ld bytes, byte-for-byte -> the kernel signs its own binaries.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORM="$HERE/form"
BIN="$FORM/form-kernel-go/bin-go"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

[ -x "$BIN" ] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)

# 1) a real signed dylib via the system linker (the oracle).
printf 'long recipe(long n){return n*3+7;}\n' > "$WORK/r.c"
clang -c "$WORK/r.c" -o "$WORK/r.o"
SDK="$(xcrun --sdk macosx --show-sdk-path)"
ld -dylib -arch arm64 -platform_version macos 11.0 11.0 \
   -o "$WORK/lib.dylib" "$WORK/r.o" -lSystem -L"$SDK/usr/lib" -syslibroot "$SDK" 2>/dev/null

# 2) extract codeLimit, ld's signing params, and ld's signature blob; emit a
#    Form program that registers the host sha256 (the four-way recipe path is
#    proven separately by tests/codesign-band.fk) and calls co-sign over the
#    real [0:codeLimit] image with ld's exact parameters.
python3 - "$WORK/lib.dylib" "$WORK/sign.fk" "$WORK/ld_blob.txt" <<'PY'
import struct, sys
dylib, fk_out, blob_out = sys.argv[1], sys.argv[2], sys.argv[3]
f = bytearray(open(dylib, 'rb').read())
ncmds = struct.unpack_from('<I', f, 16)[0]; off = 32
sig_off = sig_sz = text_vmsize = None
for _ in range(ncmds):
    cmd, csz = struct.unpack_from('<II', f, off)
    if cmd == 0x1d:                                   # LC_CODE_SIGNATURE
        sig_off, sig_sz = struct.unpack_from('<II', f, off + 8)
    if cmd == 0x19:                                   # LC_SEGMENT_64
        segname = bytes(f[off+8:off+24]).split(b'\x00')[0]
        if segname == b'__TEXT':
            text_vmsize = struct.unpack_from('<Q', f, off + 32)[0]  # vmsize
    off += csz
cd = sig_off + 20
flags = struct.unpack_from('>I', f, cd + 12)[0]
codeLimit = struct.unpack_from('>I', f, cd + 32)[0]
execSegLimit = struct.unpack_from('>Q', f, cd + 72)[0]
execSegFlags = struct.unpack_from('>Q', f, cd + 80)[0]
ioff = struct.unpack_from('>I', f, cd + 20)[0]
ident = bytes(f[cd+ioff:f.index(b'\x00', cd+ioff)])
image = list(f[:codeLimit])
identlist = list(ident)
blob = bytes(f[sig_off:sig_off + sig_sz])
open(blob_out, 'w').write(','.join(str(b) for b in blob))
with open(fk_out, 'w') as o:
    o.write('(do\n')
    o.write('  (register_jit "sha256" "sha256_bytes")\n')
    o.write('  (co-sign (list %s) %d (list %s) %d %d %d))\n' % (
        ' '.join(map(str, image)), codeLimit, ' '.join(map(str, identlist)),
        execSegLimit, flags, execSegFlags))
print("codeLimit=%d ident=%r flags=0x%x execSegLimit=0x%x execSegFlags=0x%x" % (
    codeLimit, ident.decode(), flags, execSegLimit, execSegFlags))
PY

# 3) run the Form signer and compare to ld's blob (ld pads to 8 bytes; the
#    SuperBlob content is what co-sign emits — compare on that length).
"$BIN" "$FORM/form-stdlib/sha256.fk" "$FORM/form-stdlib/form-codesign.fk" "$WORK/sign.fk" 2>/dev/null \
  | tr -dc '0-9,' | sed 's/^,//; s/,$//' > "$WORK/form_blob.txt"

python3 - "$WORK/form_blob.txt" "$WORK/ld_blob.txt" <<'PY'
import sys
form = [int(x) for x in open(sys.argv[1]).read().split(',') if x]
ld   = [int(x) for x in open(sys.argv[2]).read().split(',') if x]
n = len(form)
match = form == ld[:n]
pad_ok = all(b == 0 for b in ld[n:])
print("Form signature: %d bytes" % n)
print("ld   signature: %d bytes (%d trailing pad)" % (len(ld), len(ld) - n))
print("Form bytes == ld bytes[:%d]: %s" % (n, match))
print("ld trailing bytes all pad-zero: %s" % pad_ok)
if match and pad_ok:
    print("\nCONVICTION: the Form code-signer reproduces ld's ad-hoc signature byte-for-byte.")
    print("The gate opens — the kernel can sign its own dylibs; ld is droppable.")
    sys.exit(0)
print("\nMISMATCH — the gate stays shut.")
for i, (a, b) in enumerate(zip(form, ld)):
    if a != b:
        print("first diff at byte %d: form=%d ld=%d" % (i, a, b)); break
sys.exit(1)
PY