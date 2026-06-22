---
idea_id: idea-realization-engine
status: active
source:
  - file: form/form-stdlib/inflate.fk
    symbols: [inflate, zlib-inflate, inflate-block, inflate-syms, inflate-stored, inflate-dynamic, huff-build, huff-decode, lz-copy, br-bits, fixed-litlen-lengths]
  - file: form/form-stdlib/tests/inflate-band.fk
    symbols: []
  - file: form/form-stdlib/pdf-text.fk
    symbols: [pdf-text-file, pdf-text-bytes, collect-content, maybe-inflate, zlib?, read-paren, extract-text, after-sub, take-until]
  - file: form/form-stdlib/tests/pdf-text-band.fk
    symbols: []
  - file: form/form-stdlib/tests/pdf-text-file-band.fk
    symbols: []
  - file: form/form-stdlib/adler32.fk
    symbols: [adler32, adler32-step]
requirements:
  - "DEFLATE (RFC 1951) inflate runs as a pure Form recipe over an in-recipe byte list — stored blocks, fixed-Huffman blocks, dynamic-Huffman blocks, LZ77 back-references over a sliding window — using the bit primitives (band, bor, shl_u32, shr_u32), no host zlib. (The codec is integer by its own nature — Huffman/bit-reads/byte-copies — NOT a Form limit; the body proves fp64 four-way, incl. the native asm lane: transformer-numerics, form-asm-float.)"
  - "The inflate band crosses FOUR-WAY (Go, Rust, TypeScript, fkwu) over in-recipe fixtures covering stored/fixed(+back-ref)/dynamic blocks, an overlapping distance-1 run, and the zlib wrapper cross-checked by adler32 — verdict 31, no host I/O so fkwu sees the whole algorithm."
  - "The same `inflate` is the abstraction, not a PDF special case: it serves PNG IDAT, HTTP `deflate`, and the .zip envelope (companion to adler32's framing note)."
  - "pdf-text.fk recovers visible text from a real FlateDecode PDF: scan stream…endstream, inflate the zlib-wrapped streams (auto-detected by header), pull the Tj/TJ `( )` operands. The extraction LOGIC crosses four-way on an embedded real PDF (pdf-text-band, verdict 1)."
  - "The file-reading lane (pdf-text-file → read_file_bytes) converts multiple real PDF files off disk, proven three-way (Go/Rust/TS — host I/O is fkwu's one unsupported family): pdf-text-file-band over four fixtures, verdict 15, independently cross-checked by pdftotext."
  - "LiteParse v2.1's remaining layers — M5 layout/structure, M6 forms, M7 scanned/OCR — are named here as the path and graduate as sibling specs."
done_when:
  - 'file_contains("form/form-stdlib/inflate.fk", "defn inflate")'
  - 'file_contains("form/form-stdlib/inflate.fk", "defn huff-decode")'
  - 'file_contains("form/form-stdlib/pdf-text.fk", "defn pdf-text-file")'
  - "validate.sh reports `fourth arm: ... four-way` for the inflate band (verdict 31) and the pdf-text band (verdict 1)."
  - "validate.sh reports the pdf-text-file band converting four real PDFs three-way (verdict 15)."
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/adler32.fk form-stdlib/inflate.fk form-stdlib/tests/inflate-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/inflate.fk form-stdlib/pdf-text.fk form-stdlib/tests/pdf-text-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/inflate.fk form-stdlib/pdf-text.fk form-stdlib/tests/pdf-text-file-band.fk"
constraints:
  - "Two lanes stay separate: pure logic (inflate, stream-scan, text-pull) proves four-way over in-recipe fixtures; the file read (read_file_bytes) is honestly three-way + carrier (fkwu has no host I/O; host-io is a named unsupported family in form/fourth-arm-bands.txt). Never dress the carrier lane as four-way."
  - "One engine: the recipe that proves four-way is the recipe that crystallizes to native asm via the existing self-JIT / Form→asm lane — no hand-written C/clang inflate beside it."
  - "The text-extraction path handles the common digital PDF; cross-reference/object streams, octal/control string escapes, and /ToUnicode CMap remapping are named gaps for the robust M2/M4, not silent omissions."
  - "ASCIIHexDecode / ASCII85Decode / RunLengthDecode / LZWDecode are trivial companions; the four-way gate is on DEFLATE inflate."
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`form/form-stdlib/inflate.fk`](../form/form-stdlib/inflate.fk) (new) · reuses [`form/form-stdlib/adler32.fk`](../form/form-stdlib/adler32.fk), the grammar engine ([`bmf-grammar.fk`](../form/form-stdlib/bmf-grammar.fk), [`dynamic-grammar-carrier.fk`](../form/form-stdlib/dynamic-grammar-carrier.fk)), and the byte-walk pattern in [`wav-sense.fk`](../form/form-stdlib/wav-sense.fk)

# LiteParse v2.1 — Form-Native PDF Parsing — inflate four-way + real PDFs convert to text

## Purpose

Parse PDFs in the Form body itself, not a Python library. A PDF is **not a text
grammar** — it is a binary container holding several sub-languages. The good
news is that three of its four core layers *are* grammars, and the body already
proves "grammars-as-data, parsing-produces-recipes, one data-driven matcher"
four-way (Go/Rust/TS/fkwu). So LiteParse is mostly **authoring PDF as data over
an engine that already exists** — plus exactly one genuinely-new core recipe:
a Form-native DEFLATE inflate.

This spec proves that one recipe (M1). The full v2.1 arc is named below so the
destination is legible; M2–M7 graduate as sibling specs as each is needed.

## A PDF, by layer — and where the body already stands

| Layer | What it is | Body tissue today | New work |
|---|---|---|---|
| **1. Container / objects** | `%PDF-x.y`, `startxref`, `xref` table / xref streams, `trailer`, indirect objects `N G obj…endobj`; values are dicts `<< >>`, arrays `[ ]`, names `/F1`, numbers, strings `( )`/`< >`, refs `N G R`, bool, null | byte-walk from `wav-sense.fk` (`read_file_bytes`, LE offsets, all-int) + `bmf-grammar.fk` for the object value grammar | small grammar + xref/offset walk (M2) |
| **2. Stream decompression** | `stream…endstream` bytes — usually **FlateDecode** (zlib/DEFLATE); also LZW / ASCII85 / ASCIIHex / RunLength | `adler32.fk` *is* the zlib/DEFLATE checksum; `base64.fk` is encoding muscle | **DEFLATE inflate (M1, this spec)** — the load-bearing unknown; companions trivial |
| **3. Content-stream operators** | decompressed page body is postfix ops: `BT`, `/F1 12 Tf`, `100 700 Td`, `(Hi) Tj`, `[(W)50(orld)] TJ`, `ET` | the grammar engine — `dynamic-grammar-carrier.fk` (fks 4095), `bmf-grammar.fk` (fks 300); "one more grammar over the same engine" like form.bml / NL / shell | one grammar-as-data file → text-placement recipes (M3) |
| **4. Text recovery** | glyph codes → unicode via `/Encoding`+`Differences` and the `/ToUnicode` CMap (`beginbfchar`/`beginbfrange`) | same grammar engine — a CMap is its own little grammar | one grammar + a lookup table as data (M4) |

## Milestones (the path; M1 + the text-extraction arc are proven, M5–M7 remain)

- **M1 — DEFLATE inflate** ✓ PROVEN (`inflate.fk` + `tests/inflate-band.fk`).
  Canonical/fixed/dynamic Huffman, stored blocks, LZ77 back-references over a
  sliding window, on the bit primitives (the codec is integer by nature — see the
  float note below — not a Form limit). **Four-way, verdict 31** over in-recipe
  fixtures (stored/fixed+back-ref/dynamic/overlap/zlib⋈adler32). The only
  genuinely-new core recipe, reusable far beyond PDF (PNG, zip, HTTP).
- **M2–M4 — text extraction** ✓ PROVEN (the pragmatic content-stream-scan path,
  `pdf-text.fk` + two bands). Scan `stream…endstream`, inflate the FlateDecode
  streams (zlib-header auto-detect), pull the Tj/TJ `( )` operands. The
  extraction LOGIC is **four-way, verdict 1** on an embedded real PDF
  (`pdf-text-band`); the file-reading lane converts **four real PDF files
  three-way, verdict 15** (`pdf-text-file-band`), cross-checked by pdftotext.
  Robust M2/M4 (xref/object streams, octal escapes, /ToUnicode CMap) named as
  gaps below — this path handles the common digital PDF.
- **M5 — Layout / structure**. From the Td/Tm coordinates + font sizes captured
  in M3, reconstruct reading order, lines, paragraphs, columns, and table cells
  via geometric clustering (the body already carries cluster/manifold shapes in
  `geometric-learning.fk`).
- **M6 — Forms (AcroForm / XFA)**. `/AcroForm` field tree, widget annotations,
  field values — mostly M2 object traversal; XFA is an embedded XML stream
  (another grammar over the engine).
- **M7 — Scanned / OCR**. Image PDFs have no text layer. Decode embedded images
  (`/DCTDecode` = JPEG → reuses M1's Huffman muscle, `/CCITTFaxDecode`,
  `/JBIG2Decode`, raw) then run a vision/OCR model. **This is the largest arc and
  is explicitly its own model effort, not a parser feature** — consistent with
  the body's trajectory (whisper-tiny's full architecture already runs in Form:
  log-mel, multi-head attention, autoregressive decode), so an OCR model is the
  same north-star shape: architecture *and* weights as recipe data, four-way
  proof, native via the same JIT — never a parallel hand-written path.

Dependency chain: **M1 → M2 → (M3 → M4 text arc) → M5 layout → M6 forms.**
M7 (OCR) is independent of M2–M6 and is the heaviest; it joins once a vision
model exists in Form.

## Why M1 first

It is the only piece that is genuinely missing, it gates layers 2–6 (you can't
read most PDF streams without it), and it is the cleanest four-way band: a pure
integer recipe over a literal byte fixture, no host I/O, so all four kernels —
including fkwu — see the whole algorithm. `adler32` already proves the
checksum/framing half lives in the body; inflate completes the zlib pair. The
"simplest strange minimal" fixture: the RFC 1951 fixed-Huffman encoding of a
short string with at least one back-reference (so the LZ77 window is exercised,
not just literals) → assert the original bytes and the adler32 trailer.

## The honest host-io boundary

The *full* pipeline reading a PDF off disk needs `read_file_bytes` — a host
carrier that is 3-kernel-only (fkwu has no host I/O; it is a named unsupported
family in `form/fourth-arm-bands.txt`). LiteParse keeps two lanes separate, as
the body's discipline requires: the **logic** (inflate, grammar matching, CMap
lookup) is pure recipe proven four-way over in-recipe fixtures; the **file read**
is a thin carrier proven 3-kernel + carrier. We never dress the carrier lane as
four-way, and we never push pure logic into the carrier to avoid the boundary.

## North-star fit

One engine, not parallel paths: the recipe that proves four-way is the recipe
that crystallizes to native asm via the existing self-JIT / Form→asm lane. There
is no second native inflate to keep in sync, and no hand-written C/clang
fast-path beside the recipe — "native speed" is what the proven recipe already
becomes. The name "LiteParse v2.1" is the external handle; in the body the
carriers are honest: `inflate.fk`, `pdf-object.fk`, a content-stream grammar,
recipes, bands, a witness.

## Requirements

- [ ] `inflate.fk` decodes RFC 1951 DEFLATE as a pure Form recipe: stored blocks (BTYPE 00), fixed-Huffman blocks (BTYPE 01), and dynamic-Huffman blocks (BTYPE 10), with the code-length-code → literal/length + distance Huffman tables.
- [ ] LZ77 back-references resolve over a 32 KiB sliding window — a length/distance pair copies already-emitted bytes, including overlapping copies (distance < length).
- [ ] The recipe uses the bit primitives (`band`, `bor`, `shl_u32`, `add_u32`, shifts) and a bit-reader walking the byte list LSB-first, no host zlib. DEFLATE happens to be all-integer (Huffman/bit-reads/byte-copies) — this is a property of the codec, NOT a Form constraint: the body proves fp64 four-way including the native asm lane (`transformer-numerics`, `transformer-block`, `form-asm-float`), and LiteParse's later layers (content-stream `Tm`/`Td` matrices, layout geometry, M7 OCR) are float-bearing on that same floor.
- [ ] A canonical RFC fixture — a known DEFLATE stream with at least one back-reference — inflates bit-for-bit to its original bytes, and `adler32` of the result equals the zlib trailer value.
- [ ] The inflate band crosses FOUR-WAY (Go/Rust/TS/fkwu) with verdict 31; the fixtures are in-recipe so fkwu sees the whole algorithm (no host I/O in the proof).

## Files

- [`form/form-stdlib/inflate.fk`](../form/form-stdlib/inflate.fk) — new: the DEFLATE inflate recipe (`inflate`, `huffman-build`, `huffman-decode`, `lz77-copy`, `bitreader`).
- [`form/form-stdlib/tests/inflate-band.fk`](../form/form-stdlib/tests/inflate-band.fk) — the four-way inflate band over in-recipe fixtures, verdict 31.
- [`form/form-stdlib/pdf-text.fk`](../form/form-stdlib/pdf-text.fk) — text extraction (stream-scan + inflate + Tj/TJ pull); `tests/pdf-text-band.fk` (four-way, verdict 1) and `tests/pdf-text-file-band.fk` (three-way over four fixtures, verdict 15).
- [`form/form-stdlib/adler32.fk`](../form/form-stdlib/adler32.fk) — reused: cross-checks the inflated bytes against the zlib trailer.
- [`form/fourth-arm-bands.txt`](../form/fourth-arm-bands.txt) — add the `inflate` band row (four-way coverage floor).

## Acceptance

- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/adler32.fk form-stdlib/inflate.fk form-stdlib/tests/inflate-band.fk` reports the band with `fourth arm: ... four-way` (not `3-kernel only`).
- The band asserts `inflate(<deflate fixture>) == <original bytes>` and `adler32(<original bytes>) == <trailer>`, both as in-recipe literals — no `tests/`-side Python and no host file read.

## Verification

```bash
cd form
# M1 — inflate four-way (verdict 31)
./validate.sh form-stdlib/core.fk form-stdlib/adler32.fk form-stdlib/inflate.fk form-stdlib/tests/inflate-band.fk
# text extraction logic four-way (verdict 1)
./validate.sh form-stdlib/core.fk form-stdlib/inflate.fk form-stdlib/pdf-text.fk form-stdlib/tests/pdf-text-band.fk
# four real PDF files off disk, three-way (verdict 15)
./validate.sh form-stdlib/core.fk form-stdlib/inflate.fk form-stdlib/pdf-text.fk form-stdlib/tests/pdf-text-file-band.fk
```

Expect verdict 31 and a `fourth arm: … four-way` line for the inflate band, verdict 1 four-way for `pdf-text-band`, and verdict 15 three-way for `pdf-text-file-band` (four real PDFs off disk). A `fourth =` EMPTY result is a crash, not an unsupported op — run the fkwu binary directly without stderr suppression before characterizing it.

## Out of Scope

- M5 layout/structure, M6 forms, M7 scanned/OCR — named as the path above; each graduates as its own sibling spec.
- Robust M2/M4 (cross-reference & object streams, octal/control string escapes, /ToUnicode CMap glyph remapping) — the current text path handles the common digital PDF; these harden it for arbitrary producers.
- The four-way gate stays on pure logic; `read_file_bytes` (the off-disk lane) is three-way + carrier by design and is never counted as four-way.
- LZW / ASCII85 / ASCIIHex / RunLength companions — they may ride alongside but the proven decompressor is DEFLATE inflate.

## Risks and Assumptions

- Dynamic-Huffman table construction (the code-length-code alphabet, the 16/17/18 repeat codes) is the subtlest part; the fixture must exercise a dynamic block, not only fixed/stored, to prove it.
- Overlapping LZ77 copies (distance 1, length N — run-length fill) are a classic off-by-one; the fixture should include one.
- fkwu shares no global env across top-level forms — keep the witness computation inside ONE form, and bind descriptors as nullary `(defn X () …)`, never top-level `let` (see `self_fourth_arm_band_scope`).
- Assumes the existing bit primitives suffice for LSB-first bit reading; if a primitive is missing, it is added to the kernel floor, not worked around in the recipe.

## Known Gaps and Follow-up Tasks

- Follow-up: harden the text path into the robust M2/M4 — a proper xref/object-stream walk (`pdf-object.fk`) and /ToUnicode CMap remapping — so arbitrary-producer PDFs (object streams, non-standard encodings) convert, not only the common digital PDF.
- Follow-up: author M5 (layout/reading-order from Td/Tm coordinates) and M6 (AcroForm fields) as sibling specs.
- Follow-up: lift the bit-reader / LZ77 window into a reusable recipe when a second caller (PNG IDAT, JPEG DCTDecode) arrives.
- Gap: OCR (M7) depends on a Form-native vision model that does not yet exist; the heaviest arc, opened only when a vision model lands.
