#!/usr/bin/env bash
# form_map_demo.sh — the FULL asm-to-source mapping for a native 4th-kernel
# binary. lo-map mirrors the lowering, naming the source node that owns every
# instruction; the demo prints the whole chain for each instruction:
#   address | bytes | owning node | the node rendered as asm / source / English
# — the asm-pl-human multi-level walk applied per instruction. One tree, one
# binary, one map; the rendering levels are just packs over the same nodes.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fmap.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-lower.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hx4 (img k)
        (str_concat (hx2 (nth img k)) (str_concat (hx2 (nth img (add k 1)))
        (str_concat (hx2 (nth img (add k 2))) (hx2 (nth img (add k 3)))))))

    ; the asm-pl-human tree: if (n <= 1) then 1 else (n + (n - 1))
    (let prog (list (list 1 1 0 0) (list 2 0 0 0) (list 5 1 0 0)
                    (list 4 1 0 0) (list 3 1 3 0) (list 6 2 0 4)))
    (defn ptag (i) (nth (nth prog i) 0))
    (defn pc1  (i) (nth (nth prog i) 1))
    (defn pc2  (i) (nth (nth prog i) 2))
    (defn pc3  (i) (nth (nth prog i) 3))

    ; two render levels over the SAME nodes — each level is just a template set
    (defn rasm (i)
        (if (eq (ptag i) 1) (int_to_str (pc1 i))
        (if (eq (ptag i) 2) "ARG"
        (if (eq (ptag i) 3) (str_concat "(ADD " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) ")"))))
        (if (eq (ptag i) 4) (str_concat "(SUB " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) ")"))))
        (if (eq (ptag i) 5) (str_concat "(LE " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) ")"))))
            (str_concat "(BRZ " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) (str_concat " " (str_concat (rasm (pc3 i)) ")"))))))))))))
    (defn reng (i)
        (if (eq (ptag i) 1) (int_to_str (pc1 i))
        (if (eq (ptag i) 2) "the input n"
        (if (eq (ptag i) 3) (str_concat (reng (pc1 i)) (str_concat " plus " (reng (pc2 i))))
        (if (eq (ptag i) 4) (str_concat (reng (pc1 i)) (str_concat " minus " (reng (pc2 i))))
        (if (eq (ptag i) 5) (str_concat (reng (pc1 i)) (str_concat " is at most " (reng (pc2 i))))
            (str_concat "if " (str_concat (reng (pc1 i)) (str_concat ", then " (str_concat (reng (pc2 i)) (str_concat ", otherwise " (reng (pc3 i)))))))))))))

    (let img (lo-compile-fn prog 5))
    (let m   (lo-map-fn prog 5))

    (defn row (k)
        (print (str_concat "0x"
               (str_concat (hx2 (mul k 4))
               (str_concat "  " (str_concat (hx4 img (mul k 4))
               (str_concat "  node " (str_concat (int_to_str (nth m k))
               (str_concat "  asm " (str_concat (rasm (nth m k))
               (str_concat "   |   " (reng (nth m k)))))))))))))
    (defn rows (k)
        (if (eq k (len m)) 0 (do2 (row k) (rows (add k 1)))))
    (defn do2 (a b) b)
    (print "MAPSTART")
    (rows 0)
    0)
DRV
} > "$work/d.fk"
echo "program: if (n <= 1) then 1 else (n + (n - 1))   — the asm-pl-human tree, natively compiled"
echo
echo "addr  bytes(le)  owning source node — rendered at two levels (asm pack | English pack)"
(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null) | sed -n '/^MAPSTART$/,$p' | sed '1d' | grep -v '^0$'
echo
echo "FULL ASM-TO-SOURCE MAPPING — every instruction of the native binary traced to the"
echo "tree node that owns it; the same map serves any rendering level (any pack, any tongue)."
