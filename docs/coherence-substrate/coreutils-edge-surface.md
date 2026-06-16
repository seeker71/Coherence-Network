# Coreutils edge surface — grounded in the real source, not invented

The zero-clang Form coreutils (`cat`, `tr`, `rot13`, `head` — see
[`form-cli-offline.md`](form-cli-offline.md) "Shell commands are recipes") began as
happy-path recipes written from memory. That is *making it up*. This catalog
replaces that with the **actual behavior surface read from the canonical source**,
so every edge case is known and every Form version is measured against it — never
asserted.

## Method — three oracles, no invention

1. **Source as spec.** GNU coreutils `cat.c` (975 lines) and `tr.c` (1906 lines) are
   fetched and cached offline at `~/.coherence-network/coreutils-src/`. The option
   sets and grammars below are extracted from them, with line references.
2. **The real tool as differential oracle.** `scripts/form_coreutils_diff.sh` runs
   each Form binary and the system tool (`/bin/cat`, `/usr/bin/tr` — BSD on macOS)
   over an edge-input battery and compares **byte-for-byte**.
3. **POSIX as the common contract** where GNU and BSD diverge (noted inline).

The edge-input battery (from the source's own concerns, not picked at random):
empty input · no trailing newline · only newlines · embedded NUL bytes · high-bit /
UTF-8 bytes · a line larger than the page size (9000 bytes) · mixed content.

**Measured (2026-06-16):** 14/14 edge inputs match byte-for-byte for the operations
implemented (`cat` passthrough, `tr A-Z a-z`). A byte-at-a-time `read`/`write` loop
is inherently content-agnostic, so the *core operation* is faithful across every
byte input — the gap is the **option/mode surface**, enumerated below.

## `cat` — `cat.c` surface

| Feature | Source | Form-native |
|---|---|---|
| plain copy stdin→stdout (`simple_cat`, byte loop) | cat.c:169 | **✓ zero-clang**, matches `/bin/cat` over all edge inputs |
| file arguments; `-` = stdin; missing-file error + exit 1 | cat.c:808,822,832 | ○ stdin only (no argv, no open, no error path) |
| `-n` number-all / `-b` number-nonblank | cat.c usage | ○ |
| `-s` squeeze-blank (collapse repeated blank lines) | cat.c usage | ○ |
| `-E`/`-T`/`-A`/`-v`/`-e`/`-t` show ends/tabs/all/nonprinting | cat.c usage | ○ |
| EINTR retry, partial-write handling, page-aligned buffer, `copy_file_range`/`splice` fast paths | cat.c:182,536,597 | ○ (our loop is 1-byte, correct but unoptimized; the fast paths are an optimization, not a behavior) |

## `tr` — `tr.c` surface

**Options** (tr.c:271): `-c`/`-C` complement set1 · `-d` delete set1 · `-s`
squeeze-repeats · `-t` truncate-set1.

**SET grammar** — a SET is a sequence of these tokens (tr.c:93, `RE_*`):

| Token | Form | Source | Form-native |
|---|---|---|---|
| normal char | `x` | RE_NORMAL_CHAR | **✓** (for A–Z) |
| range | `a-z` | RE_RANGE (tr.c:684) | **✓** only `A-Z`→`a-z`; other ranges ○ |
| character class | `[:alpha:] [:upper:] [:lower:] [:digit:] [:space:] [:blank:] [:punct:] [:print:] [:graph:] [:cntrl:] [:alnum:] [:xdigit:]` | RE_CHAR_CLASS (tr.c:706) | ○ |
| equivalence class | `[=c=]` | RE_EQUIV_CLASS (tr.c:746) | ○ |
| repeat | `[c*n]` (n octal if leading 0; `[c*]` fills) | RE_REPEATED_CHAR (tr.c:724,775) | ○ |
| escapes | `\\ \a \b \f \n \r \t \v \ooo` (octal) | tr.c:321,849 | ○ (we map raw bytes, no escape parse) |

**Semantic rules** (the easy-to-get-wrong edges): SET2 is **extended to SET1's
length by repeating its last char** unless `-t` (tr.c:218); `-d` with both sets is
an error unless `-s` is also given; `-c` complements set1 against all 256 byte
values; squeeze applies to the *last* set. None of these arise for our single
`A-Z`→`a-z` map (equal-length, no options), which is why the toy matched — but they
are the surface a real `tr` must satisfy.

## `rot13`, `head` — covered, with named bounds

`rot13` (`tr A-Za-z N-ZA-Mn-za-m`) matches the system rot13 and round-trips. `head`
matches `head -n 3` but **N is hardcoded** — argv parsing (`atoi`, `-n N`) is the
shared gap for every tool that takes arguments.

## `bash` — scope, named honestly

bash is not a byte filter; it is the **POSIX shell**, and "its edge cases" are the
whole language: the lexer (quoting, here-docs, line continuation), the parser
(pipelines, lists, compound commands, functions), word expansions (brace, tilde,
parameter `${...}`, command `$(...)`, arithmetic `$((...))`, word-splitting,
filename globbing, quote removal — in that order), redirections, ~40 builtins, and
job control. Grounding that is a multi-stage arc whose honest home is the **BML
grammar + Form recipe** path (lexer→parser→evaluator), not hand-encoded asm. The
asm lane gives bash its *syscall floor* (`fork`/`exec`/`wait`/`dup2`/`pipe`, which
extend the `read`/`write`/`svc` set already proven); the language itself is grammar
work. This catalog marks the boundary so we build bash as a shell, not as a filter.

## The honest shape

The Form coreutils' **core operations are faithful** (measured byte-for-byte across
the source's own edge inputs); their **option/mode surface is the open frontier**,
now enumerated from the real source rather than guessed. Closing it is ordinary
table work — each option is more data rows + a flag check, each class a 256-entry
membership table, argv a small parse loop — with `form_coreutils_diff.sh` as the
standing oracle that every addition must pass against the real tool.
