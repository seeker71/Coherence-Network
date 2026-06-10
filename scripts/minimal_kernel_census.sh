#!/usr/bin/env bash
# minimal_kernel_census.sh — count the Go kernel's registered natives by the four
# primitive families of docs/coherence-substrate/minimal-kernel.form (intern,
# observe, offer, port) plus the named folds (figure ⊂ port-cpu, repoint ⊂
# port-ram). First-pass classification by name; the per-native registry work
# refines it. Re-run after any registerNative change so the costume count in
# the spec stays a sensing readout, not a frozen claim.
#
# Run:  scripts/minimal_kernel_census.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

grep -oE 'k\.registerNative\("[a-z_0-9]+"' "$ROOT/form/form-kernel-go/main.go" \
  | sed 's/.*("//;s/"//' | sort -u | python3 -c "
import sys, re
names = [l.strip() for l in sys.stdin if l.strip()]
families = {
  'port (axiom-4 outward)': r'(print|read_file|write_file|append_file|delete_file|list_dir|file_|stat|socket_|http_|fetch|pg_|sql|source_scan|source_inventory|volatile_cell|random|urandom|clock|time_|now|sleep|exec|jit_|spawn|env_|port_|channel_|mic_|audio_|tcp_|udp_|serve|write_form_binary|read_form_binary)',
  'intern (axioms 2+3)':    r'(intern|str_concat|list$|cons|record_new|record_set|method_define|_dict_new|_dict_set|_list_append|make_|bytes_to_recipe|str_from|compile_)',
  'observe (axiom-4 inward)': r'(head|tail|nth|len$|str_len|substring|char_at|str_find|str_line_at|str_ascii|record_get|record_has|record_keys|record_blueprint|native_blueprint|value_kind|value_str|_dict_get|_dict_has|_dict_keys|_dict_values|_get$|_in$|_iter$|node_|children|blueprint|ctor|recipe_to_bytes|serialize|str_eq|str_to_|parse_|ord|byte_to_str)',
  'figure (fold: port-cpu)': r'(add|sub|mul|div|mod|pow|eq$|gt$|ge$|lt$|le$|and$|or$|not$|neg|abs|min|max|round|floor|ceil|trunc|math_|f(add|sub|mul|div|cos|sin|exp|ln)|bor|band|bxor|bnot|shl|shr|rot|float|int_|bits|_plus|sum_bytes|seeded_bytes|string_fold)',
  'repoint (fold: port-ram)': r'(register_jit|unregister_jit|method_has|method_invoke|resolve|bind)',
  'offer/walk (axiom-5)':   r'(form_error|walk_|apply|call|choose|match|scan_run|empty)',
}
seen, rows = set(), []
for fam, pat in families.items():
    hit = [n for n in names if n not in seen and re.match(pat, n)]
    seen.update(hit); rows.append((fam, hit))
rest = [n for n in names if n not in seen]
total = len(names)
print(f'natives registered (go kernel, unique): {total}')
for fam, hit in rows:
    print(f'  {fam:26s} {len(hit):3d}')
print(f'  {\"unclassified (sugar/refine)\":26s} {len(rest):3d}  {\" \".join(rest[:10])}{\" ...\" if len(rest)>10 else \"\"}')
print()
print('every family folds into intern/observe/offer/port — see minimal-kernel.form')
"
