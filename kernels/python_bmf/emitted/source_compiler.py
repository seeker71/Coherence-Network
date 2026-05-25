"""Emitted from Form source by kernels/python_bmf/emit_python.py."""
from kernels.python_bmf.host_primitives import *  # noqa: F401, F403

def fsc_sub(s, a, b):
    return substring(s, a, b)

def is_fsc_find_string_at_len(s, needle, s_len, needle_len, i, j):
    while True:
        if (j == needle_len):
            return True
        else:
            if ((i + j) >= s_len):
                return False
            else:
                if str_eq(char_at(s, (i + j)), char_at(needle, j)):
                    s, needle, s_len, needle_len, i, j = s, needle, s_len, needle_len, i, (j + 1)
                    continue
                else:
                    return False

def is_fsc_find_string_at(s, needle, i, j):
    return is_fsc_find_string_at_len(s, needle, str_len(s), str_len(needle), i, j)

def fsc_find_string_from_len(s, needle, s_len, needle_len, i):
    while True:
        if ((i + needle_len) > s_len):
            return (0 - 1)
        else:
            if is_fsc_find_string_at_len(s, needle, s_len, needle_len, i, 0):
                return i
            else:
                s, needle, s_len, needle_len, i = s, needle, s_len, needle_len, (i + 1)
                continue

def fsc_find_string_from(s, needle, i):
    return fsc_find_string_from_len(s, needle, str_len(s), str_len(needle), i)

def is_fsc_contains(s, needle):
    return (fsc_find_string_from(s, needle, 0) >= 0)

def fsc_find_char_from_len(s, ch, s_len, i):
    while True:
        if (i >= s_len):
            return (0 - 1)
        else:
            if str_eq(char_at(s, i), ch):
                return i
            else:
                s, ch, s_len, i = s, ch, s_len, (i + 1)
                continue

def fsc_find_char_from(s, ch, i):
    return fsc_find_char_from_len(s, ch, str_len(s), i)

def is_fsc_space(ch):
    return (str_eq(ch, ' ') or (str_eq(ch, '\n') or (str_eq(ch, '\t') or str_eq(ch, '\r'))))

def fsc_skip_spaces(s, i):
    while True:
        if (i >= str_len(s)):
            return i
        else:
            if is_fsc_space(char_at(s, i)):
                s, i = s, (i + 1)
                continue
            else:
                return i

def fsc_rtrim_index(s, i):
    while True:
        if (i <= 0):
            return 0
        else:
            if is_fsc_space(char_at(s, (i - 1))):
                s, i = s, (i - 1)
                continue
            else:
                return i

def fsc_trim(s):
    start = fsc_skip_spaces(s, 0)
    end = fsc_rtrim_index(s, str_len(s))
    return ('' if (start >= end) else fsc_sub(s, start, end))

def fsc_line_end(s, i):
    e = fsc_find_char_from(s, '\n', i)
    return (str_len(s) if (e < 0) else e)

def fsc_line_next(s, i):
    e = fsc_line_end(s, i)
    return ((e + 1) if (e < str_len(s)) else e)

def is_fsc_line_opens_block(line):
    if (str_len(line) == 0):
        return False
    else:
        return str_eq(char_at(line, fsc_last_char_index(line)), '{')

def fsc_section_end_depth(s, i, depth):
    while True:
        e = fsc_line_end(s, i)
        line = fsc_trim(fsc_sub(s, i, e))
        return ((i if (depth == 0) else fsc_section_end_depth(s, fsc_line_next(s, i), (depth - 1))) if str_eq(line, '}') else (fsc_section_end_depth(s, fsc_line_next(s, i), (depth + 1)) if is_fsc_line_opens_block(line) else fsc_section_end_depth(s, fsc_line_next(s, i), depth)))

def fsc_section_end(s, i):
    return fsc_section_end_depth(s, i, 0)

def fsc_quote_loop(s, i):
    if (i >= str_len(s)):
        return ''
    else:
        ch = char_at(s, i)
        rest = fsc_quote_loop(s, (i + 1))
        return (str_concat('\\\\', rest) if str_eq(ch, '\\') else (str_concat('\\"', rest) if str_eq(ch, '"') else str_concat(ch, rest)))

def fsc_q(s):
    return str_concat('"', str_concat(fsc_quote_loop(s, 0), '"'))

def is_fsc_word_char(ch):
    cp = ord(ch)
    return (((cp >= 65) and (cp <= 90)) or (((cp >= 97) and (cp <= 122)) or (((cp >= 48) and (cp <= 57)) or (str_eq(ch, '_') or str_eq(ch, '-')))))

def is_fsc_word_start_char(ch):
    cp = ord(ch)
    return (((cp >= 65) and (cp <= 90)) or (((cp >= 97) and (cp <= 122)) or (((cp >= 48) and (cp <= 57)) or str_eq(ch, '_'))))

def is_fsc_word_loop(s, i):
    while True:
        if (i >= str_len(s)):
            return True
        else:
            if is_fsc_word_char(char_at(s, i)):
                s, i = s, (i + 1)
                continue
            else:
                return False

def is_fsc_word(s):
    if (str_len(s) > 0):
        return (is_fsc_word_start_char(char_at(s, 0)) and is_fsc_word_loop(s, 1))
    else:
        return False

def fsc_dialect_fn(dialect, suffix):
    return str_concat(dialect, str_concat('-', suffix))

def fsc_lit_fn(dialect, value):
    if str_eq(dialect, 'bmf'):
        if is_fsc_word(value):
            return 'bmf-kw'
        else:
            return 'bmf-op'
    else:
        if is_fsc_word(value):
            return fsc_dialect_fn(dialect, 'kw')
        else:
            return fsc_dialect_fn(dialect, 'op')

def fsc_literal_expr(dialect, value):
    return str_concat('(', str_concat(fsc_lit_fn(dialect, value), str_concat(' ', str_concat(fsc_q(value), ')'))))

def fsc_capture_fn(dialect, kind):
    if str_eq(dialect, 'bmf'):
        if str_eq(kind, 'string'):
            return 'bmf-string-lit'
        else:
            if str_eq(kind, 'pattern'):
                return 'bmf-pattern-lit'
            else:
                if str_eq(kind, 'rules'):
                    return 'bmf-rules-lit'
                else:
                    return 'bmf-name'
    else:
        if str_eq(kind, 'int'):
            return fsc_dialect_fn(dialect, 'int-lit')
        else:
            if str_eq(kind, 'float'):
                return fsc_dialect_fn(dialect, 'float-lit')
            else:
                if str_eq(kind, 'string'):
                    return fsc_dialect_fn(dialect, 'string-lit')
                else:
                    if str_eq(kind, 'bytes'):
                        return fsc_dialect_fn(dialect, 'bytes-lit')
                    else:
                        if str_eq(kind, 'fstring'):
                            return fsc_dialect_fn(dialect, 'fstring-lit')
                        else:
                            if str_eq(kind, 'property'):
                                return fsc_dialect_fn(dialect, 'prop')
                            else:
                                return fsc_dialect_fn(dialect, 'name')

def fsc_capture_expr(dialect, spec):
    colon = fsc_find_char_from(spec, ':', 0)
    name = fsc_sub(spec, 1, colon)
    kind = fsc_sub(spec, (colon + 1), str_len(spec))
    return str_concat('(', str_concat(fsc_capture_fn(dialect, kind), str_concat(' ', str_concat(fsc_q(name), ')'))))

def fsc_rule_ref_expr(dialect, name):
    return str_concat('(', str_concat(dialect, str_concat('-ref ', str_concat(fsc_q(name), ')'))))

def fsc_read_quoted_end(s, i):
    while True:
        if (i >= str_len(s)):
            return i
        else:
            if str_eq(char_at(s, i), '"'):
                return i
            else:
                s, i = s, (i + 1)
                continue

def fsc_read_part_end(s, i):
    while True:
        if (i >= str_len(s)):
            return i
        else:
            if is_fsc_space(char_at(s, i)):
                return i
            else:
                s, i = s, (i + 1)
                continue

def fsc_pattern_items_loop(dialect, pattern, i):
    p = fsc_skip_spaces(pattern, i)
    return ('' if (p >= str_len(pattern)) else (((e := fsc_read_quoted_end(pattern, (p + 1))), (value := fsc_sub(pattern, (p + 1), e)), str_concat(' ', str_concat(fsc_literal_expr(dialect, value), fsc_pattern_items_loop(dialect, pattern, (e + 1)))))[-1] if str_eq(char_at(pattern, p), '"') else ((e := fsc_read_part_end(pattern, p)), (part := fsc_sub(pattern, p, e)), (expr := (fsc_capture_expr(dialect, part) if str_eq(char_at(part, 0), '$') else fsc_rule_ref_expr(dialect, part))), str_concat(' ', str_concat(expr, fsc_pattern_items_loop(dialect, pattern, e))))[-1]))

def fsc_rule_line(dialect, line):
    sep = fsc_find_string_from(line, '::=', 0)
    arr = fsc_find_string_from(line, ' => ', sep)
    semi = fsc_find_char_from(line, ';', arr)
    rev = fsc_find_string_from(line, ' <= ', arr)
    name = fsc_trim(fsc_sub(line, 0, sep))
    pattern = fsc_trim(fsc_sub(line, (sep + 3), arr))
    action_end = (rev if ((rev >= 0) and (rev < semi)) else semi)
    action = fsc_trim(fsc_sub(line, (arr + 4), action_end))
    reverse = (fsc_trim(fsc_sub(line, (rev + 4), semi)) if ((rev >= 0) and (rev < semi)) else 'bmf-default-reverse-emitter')
    return str_concat('            (list ', str_concat(fsc_q(name), str_concat('\n                  (list "sequence"', str_concat(fsc_pattern_items_loop(dialect, pattern, 0), str_concat(')\n                  ', str_concat(action, str_concat('\n                  bmf-identity-inverse\n                  ', str_concat(reverse, ')'))))))))

def is_fsc_skip_rule_line(line):
    if str_eq(line, ''):
        return True
    else:
        return str_eq(char_at(line, 0), ';')

def fsc_rules_loop(dialect, body, i):
    if (i >= str_len(body)):
        return ''
    else:
        e = fsc_line_end(body, i)
        line = fsc_trim(fsc_sub(body, i, e))
        rest = fsc_rules_loop(dialect, body, fsc_line_next(body, i))
        return (rest if is_fsc_skip_rule_line(line) else str_concat(fsc_rule_line(dialect, line), str_concat('\n', rest)))

def fsc_compile_bmf_section(dialect_name, body):
    dot = fsc_find_char_from(dialect_name, '.', 0)
    dialect = fsc_sub(dialect_name, 0, dot)
    rules_name = str_concat(dialect, '-bmf-rules')
    second_name = str_concat(dialect, '-bmf-second')
    return str_concat('    (let ', str_concat(rules_name, str_concat('\n        (list\n', str_concat(fsc_rules_loop(dialect, body, 0), str_concat('        ))\n\n    (let ', str_concat(second_name, str_concat('\n        (form-bmf-second ', str_concat(fsc_q(dialect), str_concat(' (bmf-section ', str_concat(fsc_q(dialect_name), str_concat(' ', str_concat(rules_name, ')))'))))))))))))

def fsc_last_char_index(s):
    return (str_len(s) - 1)

def fsc_strip_semi(s):
    value = fsc_trim(s)
    return (value if (str_len(value) == 0) else (fsc_trim(fsc_sub(value, 0, fsc_last_char_index(value))) if str_eq(char_at(value, fsc_last_char_index(value)), ';') else value))

def is_fsc_prefix(s, prefix):
    return is_fsc_find_string_at(s, prefix, 0, 0)

def is_fsc_digit(ch):
    cp = ord(ch)
    return ((cp >= 48) and (cp <= 57))

def is_fsc_int_loop(s, i):
    while True:
        if (i >= str_len(s)):
            return True
        else:
            if is_fsc_digit(char_at(s, i)):
                s, i = s, (i + 1)
                continue
            else:
                return False

def is_fsc_int(s):
    value = fsc_trim(s)
    return (False if (str_len(value) == 0) else (((str_len(value) > 1) and is_fsc_int_loop(value, 1)) if str_eq(char_at(value, 0), '-') else is_fsc_int_loop(value, 0)))

def fsc_bml_find_comma_loop(s, i, depth, quoted):
    while True:
        if (i >= str_len(s)):
            return (0 - 1)
        else:
            ch = char_at(s, i)
            return ((fsc_bml_find_comma_loop(s, (i + 1), depth, False) if str_eq(ch, '"') else fsc_bml_find_comma_loop(s, (i + 1), depth, quoted)) if quoted else (fsc_bml_find_comma_loop(s, (i + 1), depth, True) if str_eq(ch, '"') else (fsc_bml_find_comma_loop(s, (i + 1), (depth + 1), quoted) if str_eq(ch, '(') else (fsc_bml_find_comma_loop(s, (i + 1), (depth - 1), quoted) if str_eq(ch, ')') else (i if ((depth == 0) and str_eq(ch, ',')) else fsc_bml_find_comma_loop(s, (i + 1), depth, quoted))))))

def fsc_bml_find_comma(s, i):
    return fsc_bml_find_comma_loop(s, i, 0, False)

def fsc_bml_args_form_loop(args, i):
    p = fsc_skip_spaces(args, i)
    return ('' if (p >= str_len(args)) else ((comma := fsc_bml_find_comma(args, p)), (end := (str_len(args) if (comma < 0) else comma)), (part := fsc_trim(fsc_sub(args, p, end))), (rest_start := (str_len(args) if (comma < 0) else (comma + 1))), str_concat(' ', str_concat(fsc_compile_form_bml_expr(part), fsc_bml_args_form_loop(args, rest_start))))[-1])

def fsc_bml_name_list_loop(args, i):
    p = fsc_skip_spaces(args, i)
    return ('' if (p >= str_len(args)) else ((comma := fsc_find_char_from(args, ',', p)), (end := (str_len(args) if (comma < 0) else comma)), (name := fsc_trim(fsc_sub(args, p, end))), (rest_start := (str_len(args) if (comma < 0) else (comma + 1))), str_concat(' ', str_concat(name, fsc_bml_name_list_loop(args, rest_start))))[-1])

def fsc_bml_block_end(body, i, depth):
    while True:
        e = fsc_line_end(body, i)
        line = fsc_trim(fsc_sub(body, i, e))
        return ((i if (depth == 0) else fsc_bml_block_end(body, fsc_line_next(body, i), (depth - 1))) if str_eq(line, '}') else (fsc_bml_block_end(body, fsc_line_next(body, i), (depth + 1)) if is_fsc_line_opens_block(line) else fsc_bml_block_end(body, fsc_line_next(body, i), depth)))

def is_fsc_bml_comment_line(line):
    if is_fsc_skip_rule_line(line):
        return True
    else:
        return is_fsc_prefix(line, '//')

def fsc_compile_form_bml_call(expr, open):
    close = fsc_last_char_index(expr)
    name = fsc_trim(fsc_sub(expr, 0, open))
    args = fsc_sub(expr, (open + 1), close)
    return (str_concat('(', str_concat(name, ')')) if (str_len(fsc_trim(args)) == 0) else str_concat('(', str_concat(name, str_concat(fsc_bml_args_form_loop(args, 0), ')'))))

def fsc_bml_normalize_ws_loop(s, i, quoted, saw_space):
    if (i >= str_len(s)):
        return ''
    else:
        ch = char_at(s, i)
        return (str_concat(ch, fsc_bml_normalize_ws_loop(s, (i + 1), (False if str_eq(ch, '"') else True), False)) if quoted else (str_concat(ch, fsc_bml_normalize_ws_loop(s, (i + 1), True, False)) if str_eq(ch, '"') else ((fsc_bml_normalize_ws_loop(s, (i + 1), quoted, saw_space) if saw_space else str_concat(' ', fsc_bml_normalize_ws_loop(s, (i + 1), quoted, True))) if is_fsc_space(ch) else str_concat(ch, fsc_bml_normalize_ws_loop(s, (i + 1), quoted, False)))))

def fsc_bml_normalize_ws(s):
    return fsc_trim(fsc_bml_normalize_ws_loop(s, 0, False, False))

def fsc_compile_form_bml_if(expr):
    then_pos = fsc_find_string_from(expr, ' then ', 0)
    else_pos = fsc_find_string_from(expr, ' else ', then_pos)
    cond = fsc_trim(fsc_sub(expr, 3, then_pos))
    yes = fsc_trim(fsc_sub(expr, (then_pos + 6), else_pos))
    no = fsc_trim(fsc_sub(expr, (else_pos + 6), str_len(expr)))
    return str_concat('(if ', str_concat(fsc_compile_form_bml_expr(cond), str_concat(' ', str_concat(fsc_compile_form_bml_expr(yes), str_concat(' ', str_concat(fsc_compile_form_bml_expr(no), ')'))))))

def fsc_compile_form_bml_expr(raw):
    expr = fsc_bml_normalize_ws(fsc_strip_semi(raw))
    open = fsc_find_char_from(expr, '(', 0)
    return ('(empty)' if (str_len(expr) == 0) else (fsc_compile_form_bml_if(expr) if is_fsc_prefix(expr, 'if ') else (fsc_compile_form_bml_call(expr, open) if ((open >= 0) and str_eq(char_at(expr, fsc_last_char_index(expr)), ')')) else ('(empty)' if str_eq(expr, 'empty') else ('true' if str_eq(expr, 'true') else ('false' if str_eq(expr, 'false') else ('null' if str_eq(expr, 'null') else (expr if is_fsc_int(expr) else expr))))))))

def fsc_compile_form_bml_def(line):
    open = fsc_find_char_from(line, '(', 4)
    close = fsc_find_char_from(line, ')', open)
    eq_pos = fsc_find_char_from(line, '=', close)
    name = fsc_trim(fsc_sub(line, 4, open))
    args = fsc_sub(line, (open + 1), close)
    body = fsc_sub(line, (eq_pos + 1), str_len(line))
    return str_concat('    (defn ', str_concat(name, str_concat(' (', str_concat(fsc_trim(fsc_bml_name_list_loop(args, 0)), str_concat(')\n        ', str_concat(fsc_compile_form_bml_expr(body), ')\n'))))))

def fsc_compile_form_bml_let(line):
    eq_pos = fsc_find_char_from(line, '=', 4)
    name = fsc_trim(fsc_sub(line, 4, eq_pos))
    body = fsc_sub(line, (eq_pos + 1), str_len(line))
    return str_concat('    (let ', str_concat(name, str_concat(' ', str_concat(fsc_compile_form_bml_expr(body), ')\n'))))

def fsc_compile_form_bml_block_line(line):
    value = fsc_strip_semi(line)
    return ('' if is_fsc_bml_comment_line(value) else (((eq_pos := fsc_find_char_from(value, '=', 4)), (name := fsc_trim(fsc_sub(value, 4, eq_pos))), (body := fsc_sub(value, (eq_pos + 1), str_len(value))), str_concat('        (let ', str_concat(name, str_concat(' ', str_concat(fsc_compile_form_bml_expr(body), ')\n')))))[-1] if is_fsc_prefix(value, 'let ') else str_concat('        ', str_concat(fsc_compile_form_bml_expr(value), '\n'))))

def fsc_bml_stmt_end_loop(body, i, end, depth, quoted):
    while True:
        if (i >= end):
            return end
        else:
            ch = char_at(body, i)
            return ((fsc_bml_stmt_end_loop(body, (i + 1), end, depth, False) if str_eq(ch, '"') else fsc_bml_stmt_end_loop(body, (i + 1), end, depth, quoted)) if quoted else (fsc_bml_stmt_end_loop(body, (i + 1), end, depth, True) if str_eq(ch, '"') else (fsc_bml_stmt_end_loop(body, (i + 1), end, (depth + 1), quoted) if str_eq(ch, '(') else (fsc_bml_stmt_end_loop(body, (i + 1), end, (depth - 1), quoted) if str_eq(ch, ')') else ((i + 1) if ((depth == 0) and str_eq(ch, ';')) else fsc_bml_stmt_end_loop(body, (i + 1), end, depth, quoted))))))

def fsc_bml_stmt_end(body, i, end):
    return fsc_bml_stmt_end_loop(body, i, end, 0, False)

def fsc_compile_form_bml_block_stmts(body, i, end):
    p = fsc_skip_spaces(body, i)
    return ('' if (p >= end) else ((line_end := fsc_line_end(body, p)), (line := fsc_trim(fsc_sub(body, p, line_end))), (fsc_compile_form_bml_block_stmts(body, fsc_line_next(body, p), end) if is_fsc_bml_comment_line(line) else ((stmt_end := fsc_bml_stmt_end(body, p, end)), (stmt := fsc_trim(fsc_sub(body, p, stmt_end))), str_concat(fsc_compile_form_bml_block_line(stmt), fsc_compile_form_bml_block_stmts(body, stmt_end, end)))[-1]))[-1])

def fsc_compile_form_bml_block_lines(body, i, end):
    return fsc_compile_form_bml_block_stmts(body, i, end)

def fsc_compile_form_bml_def_block(body, line, body_start):
    open = fsc_find_char_from(line, '(', 4)
    close = fsc_find_char_from(line, ')', open)
    name = fsc_trim(fsc_sub(line, 4, open))
    args = fsc_sub(line, (open + 1), close)
    body_end = fsc_bml_block_end(body, body_start, 0)
    return str_concat('    (defn ', str_concat(name, str_concat(' (', str_concat(fsc_trim(fsc_bml_name_list_loop(args, 0)), str_concat(')\n', str_concat('        (do\n', str_concat(fsc_compile_form_bml_block_lines(body, body_start, body_end), '        ))\n')))))))

def fsc_compile_form_bml_line(line):
    value = fsc_strip_semi(line)
    return ('' if is_fsc_bml_comment_line(value) else (fsc_compile_form_bml_def(value) if is_fsc_prefix(value, 'def ') else (fsc_compile_form_bml_let(value) if is_fsc_prefix(value, 'let ') else str_concat('    ', str_concat(fsc_compile_form_bml_expr(value), '\n')))))

def fsc_form_bml_lines_loop(body, i):
    if (i >= str_len(body)):
        return ''
    else:
        e = fsc_line_end(body, i)
        line = fsc_trim(fsc_sub(body, i, e))
        return (((body_start := fsc_line_next(body, i)), (body_end := fsc_bml_block_end(body, body_start, 0)), str_concat(fsc_compile_form_bml_def_block(body, line, body_start), fsc_form_bml_lines_loop(body, fsc_line_next(body, body_end))))[-1] if (is_fsc_prefix(line, 'def ') and is_fsc_line_opens_block(line)) else str_concat(fsc_compile_form_bml_line(line), fsc_form_bml_lines_loop(body, fsc_line_next(body, i))))

def fsc_compile_form_bml_section(body):
    return str_concat('(do\n', str_concat(fsc_form_bml_lines_loop(body, 0), ')\n'))

def is_fsc_form_action_dialect(dialect_name):
    return (str_eq(dialect_name, 'form.bml') or str_eq(dialect_name, 'form.action'))

def fsc_compile_section(dialect_name, body):
    if is_fsc_form_action_dialect(dialect_name):
        return fsc_compile_form_bml_section(body)
    else:
        return fsc_compile_bmf_section(dialect_name, body)

def fsc_action_src_kw(value):
    return bmf_atom('form-action-keyword', value)

def fsc_action_src_name(value):
    return bmf_atom('form-action-name', value)

def fsc_action_src_int(value):
    return bmf_atom('form-action-int', value)

def fsc_action_src_string(value):
    return bmf_atom('form-action-string', value)

def fsc_action_src_op(value):
    return bmf_atom('form-action-op', value)

def fsc_action_src_params(value):
    return bmf_atom('form-action-params', value)

def fsc_action_src_args(value):
    return bmf_atom('form-action-args', value)

def fsc_action_src_expr(value):
    return bmf_atom('form-action-expr', value)

def fsc_action_src_items(value):
    return bmf_atom('form-action-items', value)

def fsc_source_cursor_with_len(source, offset, line, col, source_len):
    return ['fsc-source-cursor', source, offset, line, col, source_len]

def fsc_file_source_cursor(path, offset, line, col, source_len):
    return ['fsc-file-source-cursor', path, offset, line, col, source_len]

def fsc_file_source_cursor_window(path, offset, line, col, source_len, window_start, window):
    return ['fsc-file-source-cursor-window', path, offset, line, col, source_len, window_start, window]

def is_fsc_source_cursor_file(cursor):
    return ((len(cursor) > 0) and (str_eq(cursor[0], 'fsc-file-source-cursor') or str_eq(cursor[0], 'fsc-file-source-cursor-window')))

def is_fsc_source_cursor_file_window(cursor):
    return ((len(cursor) > 0) and str_eq(cursor[0], 'fsc-file-source-cursor-window'))

def fsc_source_cursor(source, offset, line, col):
    return fsc_source_cursor_with_len(source, offset, line, col, str_len(source))

def fsc_source_cursor_source(cursor):
    return cursor[1]

def fsc_source_cursor_offset(cursor):
    return cursor[2]

def fsc_source_cursor_line(cursor):
    return cursor[3]

def fsc_source_cursor_col(cursor):
    return cursor[4]

def fsc_source_cursor_source_len(cursor):
    if (len(cursor) > 5):
        return cursor[5]
    else:
        if is_fsc_source_cursor_file(cursor):
            return file_size(fsc_source_cursor_source(cursor))
        else:
            return str_len(fsc_source_cursor_source(cursor))

def fsc_source_window_size():
    return 4096

def fsc_source_cursor_window_start(cursor):
    return cursor[6]

def fsc_source_cursor_window(cursor):
    return cursor[7]

def is_fsc_source_cursor_window_contains(cursor, offset):
    return (is_fsc_source_cursor_file_window(cursor) and ((offset >= fsc_source_cursor_window_start(cursor)) and (offset < (fsc_source_cursor_window_start(cursor) + str_len(fsc_source_cursor_window(cursor))))))

def fsc_source_cursor_windowed(cursor):
    if is_fsc_source_cursor_window_contains(cursor, fsc_source_cursor_offset(cursor)):
        return cursor
    else:
        return fsc_file_source_cursor_window(fsc_source_cursor_source(cursor), fsc_source_cursor_offset(cursor), fsc_source_cursor_line(cursor), fsc_source_cursor_col(cursor), fsc_source_cursor_source_len(cursor), fsc_source_cursor_offset(cursor), read_file_slice(fsc_source_cursor_source(cursor), fsc_source_cursor_offset(cursor), fsc_source_window_size()))

def is_fsc_source_cursor_end(cursor):
    return (fsc_source_cursor_offset(cursor) >= fsc_source_cursor_source_len(cursor))

def fsc_source_cursor_char(cursor):
    if is_fsc_source_cursor_end(cursor):
        return ''
    else:
        if is_fsc_source_cursor_file(cursor):
            windowed = fsc_source_cursor_windowed(cursor)
            return char_at(fsc_source_cursor_window(windowed), (fsc_source_cursor_offset(cursor) - fsc_source_cursor_window_start(windowed)))
        else:
            return char_at(fsc_source_cursor_source(cursor), fsc_source_cursor_offset(cursor))

def fsc_source_cursor_next(cursor, offset, line, col):
    if is_fsc_source_cursor_file(cursor):
        if (is_fsc_source_cursor_file_window(cursor) and is_fsc_source_cursor_window_contains(cursor, offset)):
            return fsc_file_source_cursor_window(fsc_source_cursor_source(cursor), offset, line, col, fsc_source_cursor_source_len(cursor), fsc_source_cursor_window_start(cursor), fsc_source_cursor_window(cursor))
        else:
            return fsc_file_source_cursor(fsc_source_cursor_source(cursor), offset, line, col, fsc_source_cursor_source_len(cursor))
    else:
        return fsc_source_cursor_with_len(fsc_source_cursor_source(cursor), offset, line, col, fsc_source_cursor_source_len(cursor))

def fsc_source_cursor_advance(cursor):
    ch = fsc_source_cursor_char(cursor)
    return (fsc_source_cursor_next(cursor, (fsc_source_cursor_offset(cursor) + 1), (fsc_source_cursor_line(cursor) + 1), 0) if str_eq(ch, '\n') else fsc_source_cursor_next(cursor, (fsc_source_cursor_offset(cursor) + 1), fsc_source_cursor_line(cursor), (fsc_source_cursor_col(cursor) + 1)))

def fsc_source_cursor_range(start, end):
    return ['fsc-source-range', fsc_source_cursor_offset(start), (fsc_source_cursor_offset(end) - fsc_source_cursor_offset(start)), fsc_source_cursor_line(start), fsc_source_cursor_col(start), fsc_source_cursor_line(end), fsc_source_cursor_col(end)]

def fsc_source_object(kind, value, start, end):
    return bmf_object(kind, value, bmf_match_source(bmf_empty(0), [fsc_source_cursor_range(start, end)]), bmf_identity_inverse)

def fsc_scan_result(object, cursor):
    return ['fsc-scan-result', object, cursor]

def fsc_scan_result_object(result):
    return result[1]

def fsc_scan_result_cursor(result):
    return result[2]

def is_fsc_string_list_contains(xs, value):
    while True:
        if is_nil(xs):
            return False
        else:
            if str_eq(xs[0], value):
                return True
            else:
                xs, value = xs[1:], value
                continue

def fsc_source_scan_skip(cursor):
    while True:
        if is_fsc_source_cursor_end(cursor):
            return cursor
        else:
            if is_fsc_space(fsc_source_cursor_char(cursor)):
                cursor = fsc_source_cursor_advance(cursor)
                continue
            else:
                return cursor

def is_fsc_source_name_char(ch):
    return (is_fsc_word_char(ch) or str_eq(ch, '?'))

def is_fsc_source_name_start_char(ch):
    cp = ord(ch)
    return (((cp >= 65) and (cp <= 90)) or (((cp >= 97) and (cp <= 122)) or str_eq(ch, '_')))

def fsc_source_scan_name_loop(cursor, value):
    while True:
        if is_fsc_source_cursor_end(cursor):
            return [value, cursor]
        else:
            ch = fsc_source_cursor_char(cursor)
            return (fsc_source_scan_name_loop(fsc_source_cursor_advance(cursor), str_concat(value, ch)) if is_fsc_source_name_char(ch) else [value, cursor])

def fsc_source_name_kind(value, keywords, keyword_kind, name_kind):
    if is_fsc_string_list_contains(keywords, value):
        return keyword_kind
    else:
        return name_kind

def fsc_source_dialect(keywords, keyword_kind, name_kind, int_kind, string_kind, op_kind, eof_kind, ops):
    return ['fsc-source-dialect', keywords, keyword_kind, name_kind, int_kind, string_kind, op_kind, eof_kind, ops]

def fsc_source_dialect_keywords(dialect):
    return dialect[1]

def fsc_source_dialect_keyword_kind(dialect):
    return dialect[2]

def fsc_source_dialect_name_kind(dialect):
    return dialect[3]

def fsc_source_dialect_int_kind(dialect):
    return dialect[4]

def fsc_source_dialect_string_kind(dialect):
    return dialect[5]

def fsc_source_dialect_op_kind(dialect):
    return dialect[6]

def fsc_source_dialect_eof_kind(dialect):
    return dialect[7]

def fsc_source_dialect_ops(dialect):
    return dialect[8]

def is_fsc_action_keyword(value):
    return (str_eq(value, 'def') or (str_eq(value, 'let') or (str_eq(value, 'if') or (str_eq(value, 'then') or (str_eq(value, 'else') or str_eq(value, 'do'))))))

def fsc_action_name_kind(value):
    if is_fsc_action_keyword(value):
        return 'form-action-keyword'
    else:
        return 'form-action-name'

def fsc_source_scan_name(start, keywords, keyword_kind, name_kind):
    read = fsc_source_scan_name_loop(start, '')
    value = read[0]
    end = read[1]
    return fsc_scan_result(fsc_source_object(fsc_source_name_kind(value, keywords, keyword_kind, name_kind), value, start, end), end)

def fsc_source_scan_int_loop(cursor, value):
    while True:
        if is_fsc_source_cursor_end(cursor):
            return [value, cursor]
        else:
            ch = fsc_source_cursor_char(cursor)
            return (fsc_source_scan_int_loop(fsc_source_cursor_advance(cursor), str_concat(value, ch)) if is_fsc_digit(ch) else [value, cursor])

def fsc_source_scan_int(start, int_kind):
    read = fsc_source_scan_int_loop(start, '')
    value = read[0]
    end = read[1]
    return fsc_scan_result(fsc_source_object(int_kind, value, start, end), end)

def fsc_source_scan_string_loop(cursor, value):
    while True:
        if is_fsc_source_cursor_end(cursor):
            return [value, cursor]
        else:
            if str_eq(fsc_source_cursor_char(cursor), '"'):
                return [value, fsc_source_cursor_advance(cursor)]
            else:
                cursor, value = fsc_source_cursor_advance(cursor), str_concat(value, fsc_source_cursor_char(cursor))
                continue

def fsc_source_scan_string(start, string_kind):
    body_start = fsc_source_cursor_advance(start)
    read = fsc_source_scan_string_loop(body_start, '')
    value = read[0]
    end = read[1]
    return fsc_scan_result(fsc_source_object(string_kind, value, start, end), end)

def fsc_source_advance_n(cursor, n):
    while True:
        if (n <= 0):
            return cursor
        else:
            cursor, n = fsc_source_cursor_advance(cursor), (n - 1)
            continue

def is_fsc_source_cursor_prefix(cursor, prefix):
    offset = fsc_source_cursor_offset(cursor)
    return (is_fsc_source_cursor_file_prefix(cursor, prefix, 0) if is_fsc_source_cursor_file(cursor) else is_fsc_find_string_at_len(fsc_source_cursor_source(cursor), prefix, fsc_source_cursor_source_len(cursor), str_len(prefix), offset, 0))

def is_fsc_source_cursor_file_prefix(cursor, prefix, j):
    while True:
        if (j == str_len(prefix)):
            return True
        else:
            if ((fsc_source_cursor_offset(cursor) + j) >= fsc_source_cursor_source_len(cursor)):
                return False
            else:
                if (file_byte_at(fsc_source_cursor_source(cursor), (fsc_source_cursor_offset(cursor) + j)) == ord(char_at(prefix, j))):
                    cursor, prefix, j = cursor, prefix, (j + 1)
                    continue
                else:
                    return False

def fsc_source_match_op(cursor, ops):
    while True:
        if is_nil(ops):
            return fsc_source_cursor_char(cursor)
        else:
            if is_fsc_source_cursor_prefix(cursor, ops[0]):
                return ops[0]
            else:
                cursor, ops = cursor, ops[1:]
                continue

def fsc_source_scan_op(start, op_kind, ops):
    value = fsc_source_match_op(start, ops)
    end = fsc_source_advance_n(start, str_len(value))
    return fsc_scan_result(fsc_source_object(op_kind, value, start, end), end)

def fsc_source_scan_next(cursor, keywords, keyword_kind, name_kind, int_kind, string_kind, op_kind, eof_kind, ops):
    start = fsc_source_scan_skip(cursor)
    ch = fsc_source_cursor_char(start)
    return (fsc_scan_result(fsc_source_object(eof_kind, '', start, start), start) if is_fsc_source_cursor_end(start) else (fsc_source_scan_string(start, string_kind) if str_eq(ch, '"') else (fsc_source_scan_int(start, int_kind) if is_fsc_digit(ch) else (fsc_source_scan_name(start, keywords, keyword_kind, name_kind) if is_fsc_source_name_start_char(ch) else fsc_source_scan_op(start, op_kind, ops)))))

def fsc_source_scan_next_dialect(cursor, dialect):
    return fsc_source_scan_next(cursor, fsc_source_dialect_keywords(dialect), fsc_source_dialect_keyword_kind(dialect), fsc_source_dialect_name_kind(dialect), fsc_source_dialect_int_kind(dialect), fsc_source_dialect_string_kind(dialect), fsc_source_dialect_op_kind(dialect), fsc_source_dialect_eof_kind(dialect), fsc_source_dialect_ops(dialect))

def fsc_action_scan_skip(cursor):
    return fsc_source_scan_skip(cursor)

def is_fsc_action_name_char(ch):
    return is_fsc_source_name_char(ch)

def fsc_action_scan_name_loop(cursor, value):
    return fsc_source_scan_name_loop(cursor, value)

def fsc_action_scan_name(start):
    return fsc_source_scan_name(start, fsc_action_keywords, 'form-action-keyword', 'form-action-name')

def fsc_action_scan_int_loop(cursor, value):
    return fsc_source_scan_int_loop(cursor, value)

def fsc_action_scan_int(start):
    return fsc_source_scan_int(start, 'form-action-int')

def fsc_action_scan_string_loop(cursor, value):
    return fsc_source_scan_string_loop(cursor, value)

def fsc_action_scan_string(start):
    return fsc_source_scan_string(start, 'form-action-string')

def fsc_action_scan_op(start):
    return fsc_source_scan_op(start, 'form-action-op', fsc_common_op2)

def fsc_action_scan_next(cursor):
    return fsc_source_scan_next_dialect(cursor, fsc_action_source_dialect)

def fsc_action_kw(value):
    return object_lit('form-action-keyword', value)

def fsc_action_op(value):
    return object_lit('form-action-op', value)

def fsc_action_name(capture_name):
    return ['capture', capture_name, object_lit('form-action-name', '')]

def fsc_action_int(capture_name):
    return ['capture', capture_name, object_lit('form-action-int', '')]

def fsc_action_string(capture_name):
    return ['capture', capture_name, object_lit('form-action-string', '')]

def fsc_action_params(capture_name):
    return ['capture', capture_name, object_lit('form-action-params', '')]

def fsc_action_args(capture_name):
    return ['capture', capture_name, object_lit('form-action-args', '')]

def fsc_action_expr(capture_name):
    return ['capture', capture_name, object_lit('form-action-expr', '')]

def fsc_action_items(capture_name):
    return ['capture', capture_name, object_lit('form-action-items', '')]

def fsc_action_cap(objects, capture_name):
    return bmf_collection_value(objects, capture_name)

def fsc_action_ident_node(name):
    return intern_node(FSC_ACTION_IDENT, [intern_trivial_string(name)])

def fsc_action_param_nodes(param_list):
    if is_nil(param_list):
        return empty()
    else:
        return [intern_trivial_string(param_list[0]), *fsc_action_param_nodes(param_list[1:])]

def fsc_action_param_block(param_list):
    return intern_node(FSC_ACTION_BLOCK_SEQ, fsc_action_param_nodes(param_list))

def fsc_action_call_node(name, args):
    if str_eq(name, 'add'):
        return intern_node(FSC_ACTION_MATH_ADD, args)
    else:
        if str_eq(name, 'sub'):
            return intern_node(FSC_ACTION_MATH_SUB, args)
        else:
            if str_eq(name, 'mul'):
                return intern_node(FSC_ACTION_MATH_MUL, args)
            else:
                if str_eq(name, 'mod'):
                    return intern_node(FSC_ACTION_MATH_MOD, args)
                else:
                    if str_eq(name, 'eq'):
                        return intern_node(FSC_ACTION_COMPARE_EQ, args)
                    else:
                        if str_eq(name, 'lt'):
                            return intern_node(FSC_ACTION_COMPARE_LT, args)
                        else:
                            if str_eq(name, 'le'):
                                return intern_node(FSC_ACTION_COMPARE_LE, args)
                            else:
                                if str_eq(name, 'gt'):
                                    return intern_node(FSC_ACTION_COMPARE_GT, args)
                                else:
                                    if str_eq(name, 'ge'):
                                        return intern_node(FSC_ACTION_COMPARE_GE, args)
                                    else:
                                        return intern_node(FSC_ACTION_FNCALL, [intern_trivial_string(name), *args])

def fsc_action_let_node(name, value):
    return intern_node(FSC_ACTION_BLOCK_LET, [intern_trivial_string(name), value])

def fsc_action_do_node(items):
    return intern_node(FSC_ACTION_BLOCK_DO, items)

def fsc_action_if_node(cond, yes, no):
    return intern_node(FSC_ACTION_COND_IF, [cond, yes, no])

def fsc_action_emit_ident(objects):
    return fsc_action_ident_node(fsc_action_cap(objects, 'name'))

def fsc_action_emit_int(objects):
    return intern_trivial_int(str_to_int(fsc_action_cap(objects, 'value')))

def fsc_action_emit_string(objects):
    return intern_trivial_string(fsc_action_cap(objects, 'value'))

def fsc_action_emit_call(objects):
    return fsc_action_call_node(fsc_action_cap(objects, 'name'), fsc_action_cap(objects, 'args'))

def fsc_action_emit_let(objects):
    return fsc_action_let_node(fsc_action_cap(objects, 'name'), fsc_action_cap(objects, 'value'))

def fsc_action_emit_if(objects):
    return fsc_action_if_node(fsc_action_cap(objects, 'cond'), fsc_action_cap(objects, 'yes'), fsc_action_cap(objects, 'no'))

def fsc_action_emit_def(objects):
    return intern_node(FSC_ACTION_FNDEF, [intern_trivial_string(fsc_action_cap(objects, 'name')), fsc_action_param_block(fsc_action_cap(objects, 'params')), fsc_action_cap(objects, 'body')])

def fsc_action_emit_do(objects):
    return fsc_action_do_node(fsc_action_cap(objects, 'items'))

def fsc_action_source_span(object):
    return bmf_object_source_span(object)

def form_action_bmf_rules(_x):
    return [['ident', fsc_action_name('name'), fsc_action_emit_ident, bmf_identity_inverse, fsc_action_source_span], ['int', fsc_action_int('value'), fsc_action_emit_int, bmf_identity_inverse, fsc_action_source_span], ['string', fsc_action_string('value'), fsc_action_emit_string, bmf_identity_inverse, fsc_action_source_span], ['call', ['sequence', fsc_action_name('name'), fsc_action_args('args')], fsc_action_emit_call, bmf_identity_inverse, fsc_action_source_span], ['if', ['sequence', fsc_action_kw('if'), fsc_action_expr('cond'), fsc_action_kw('then'), fsc_action_expr('yes'), fsc_action_kw('else'), fsc_action_expr('no')], fsc_action_emit_if, bmf_identity_inverse, fsc_action_source_span], ['let', ['sequence', fsc_action_kw('let'), fsc_action_name('name'), fsc_action_op('='), fsc_action_expr('value'), fsc_action_op(';')], fsc_action_emit_let, bmf_identity_inverse, fsc_action_source_span], ['def', ['sequence', fsc_action_kw('def'), fsc_action_name('name'), fsc_action_params('params'), fsc_action_op('='), fsc_action_expr('body'), fsc_action_op(';')], fsc_action_emit_def, bmf_identity_inverse, fsc_action_source_span], ['do', ['sequence', fsc_action_kw('do'), fsc_action_items('items')], fsc_action_emit_do, bmf_identity_inverse, fsc_action_source_span]]

def form_action_bmf_find_rule(name, rules):
    while True:
        if is_nil(rules):
            return empty()
        else:
            if str_eq(rule_name(rules[0]), name):
                return rules[0]
            else:
                name, rules = name, rules[1:]
                continue

def apply_form_action_bmf_rule(rule_name, objects):
    return apply_object_rule(form_action_bmf_find_rule(rule_name, form_action_bmf_rules(0)), objects)

def form_action_bmf_value(rule_name, objects):
    return bmf_object_value(cap_get(match_caps(apply_form_action_bmf_rule(rule_name, objects)), 'result'))

def form_action_bmf_ident(name):
    return form_action_bmf_value('ident', [fsc_action_src_name(name)])

def form_action_bmf_int(value):
    return form_action_bmf_value('int', [fsc_action_src_int(value)])

def form_action_bmf_string(value):
    return form_action_bmf_value('string', [fsc_action_src_string(value)])

def form_action_bmf_call(name, args):
    return form_action_bmf_value('call', [fsc_action_src_name(name), fsc_action_src_args(args)])

def form_action_bmf_call0(name):
    return form_action_bmf_call(name, empty())

def form_action_bmf_call1(name, a):
    return form_action_bmf_call(name, [a])

def form_action_bmf_call2(name, a, b):
    return form_action_bmf_call(name, [a, b])

def form_action_bmf_call3(name, a, b, c):
    return form_action_bmf_call(name, [a, b, c])

def form_action_bmf_call4(name, a, b, c, d):
    return form_action_bmf_call(name, [a, b, c, d])

def form_action_bmf_call5(name, a, b, c, d, e):
    return form_action_bmf_call(name, [a, b, c, d, e])

def form_action_bmf_if(cond, yes, no):
    return form_action_bmf_value('if', [fsc_action_src_kw('if'), fsc_action_src_expr(cond), fsc_action_src_kw('then'), fsc_action_src_expr(yes), fsc_action_src_kw('else'), fsc_action_src_expr(no)])

def form_action_bmf_let(name, value):
    return form_action_bmf_value('let', [fsc_action_src_kw('let'), fsc_action_src_name(name), fsc_action_src_op('='), fsc_action_src_expr(value), fsc_action_src_op(';')])

def form_action_bmf_def(name, param_list, body):
    return form_action_bmf_value('def', [fsc_action_src_kw('def'), fsc_action_src_name(name), fsc_action_src_params(param_list), fsc_action_src_op('='), fsc_action_src_expr(body), fsc_action_src_op(';')])

def form_action_bmf_do_source(items):
    return [fsc_action_src_kw('do'), fsc_action_src_items(items)]

def form_action_bmf_do_roundtrip(items):
    return bmf_roundtrip(form_action_bmf_find_rule('do', form_action_bmf_rules(0)), form_action_bmf_do_source(items))

def form_action_bmf_roundtrip_program(rt):
    return bmf_object_value(bmf_roundtrip_first_object(rt))

def form_action_bmf_program(items):
    return form_action_bmf_roundtrip_program(form_action_bmf_do_roundtrip(items))

def form_action_bmf_proof_score(payload, rt, program):
    return (payload + ((100 if is_bmf_roundtrip_node_eq(rt) else 0) + (len(form_action_bmf_rules(0)) + len(node_children(program)))))

def fsc_source_corpus(name, files):
    return compiler_object('fsc-source-corpus', [name, files], files, compiler_identity_inverse)

def fsc_source_corpus_name(corpus):
    return compiler_object_value(corpus)[0]

def fsc_source_corpus_files(corpus):
    return compiler_object_value(corpus)[1]

def fsc_source_file(path, kind, sections):
    return compiler_object('fsc-source-file', [path, kind, sections], sections, compiler_identity_inverse)

def fsc_source_file_path(file):
    return compiler_object_value(file)[0]

def fsc_source_file_kind(file):
    return compiler_object_value(file)[1]

def fsc_source_file_sections(file):
    return compiler_object_value(file)[2]

def fsc_source_section_binary(dialect, rule_name, source_stream, binary):
    return compiler_object('fsc-source-section-binary', [dialect, rule_name, source_stream, binary], source_stream, compiler_identity_inverse)

def fsc_source_section_dialect(section):
    return compiler_object_value(section)[0]

def fsc_source_section_rule_name(section):
    return compiler_object_value(section)[1]

def fsc_source_section_source(section):
    return compiler_object_value(section)[2]

def fsc_source_section_binary_node(section):
    return compiler_object_value(section)[3]

def is_fsc_source_section_node_eq(section, node):
    return node_eq(fsc_source_section_binary_node(section), node)

def fsc_repo_file(path, kind, media_type, byte_count, sensed):
    return compiler_object('fsc-repo-file', [path, kind, media_type, byte_count, sensed], sensed, compiler_identity_inverse)

def fsc_repo_file_from_text(path, kind, media_type, text, sensed):
    return fsc_repo_file(path, kind, media_type, str_len(text), sensed)

def fsc_repo_file_from_bytes(path, kind, media_type, bytes, sensed):
    return fsc_repo_file(path, kind, media_type, len(bytes), sensed)

def fsc_repo_file_path(file):
    return compiler_object_value(file)[0]

def fsc_repo_file_kind(file):
    return compiler_object_value(file)[1]

def fsc_repo_file_media_type(file):
    return compiler_object_value(file)[2]

def fsc_repo_file_byte_count(file):
    return compiler_object_value(file)[3]

def fsc_repo_file_sensed(file):
    return compiler_object_value(file)[4]

def fsc_repo_field_int(field, value):
    return intern_node(FSC_REPO_MEANING_FIELD, [field, intern_trivial_int(value)])

def fsc_repo_field_string(field, value):
    return intern_node(FSC_REPO_MEANING_FIELD, [field, intern_trivial_string(value)])

def fsc_repo_field_node(field, value):
    return intern_node(FSC_REPO_MEANING_FIELD, [field, value])

def fsc_repo_meaning(decoder, fields):
    return intern_node(FSC_REPO_MEANING, [decoder, *fields])

def fsc_repo_meaning_decoder(meaning):
    return node_children(meaning)[0]

def fsc_repo_meaning_fields(meaning):
    return node_children(meaning)[1:]

def fsc_repo_field_key(field):
    return node_children(field)[0]

def fsc_repo_field_value(field):
    return node_children(field)[1]

def fsc_repo_field_value_int(field):
    return node_value(fsc_repo_field_value(field))

def fsc_repo_field_value_string(field):
    return node_value(fsc_repo_field_value(field))

def fsc_repo_text_line(offset, length, start_line, start_col, end_line, end_col):
    return intern_node(FSC_REPO_TEXT_LINE, [intern_trivial_int(offset), intern_trivial_int(length), intern_trivial_int(start_line), intern_trivial_int(start_col), intern_trivial_int(end_line), intern_trivial_int(end_col)])

def fsc_repo_text_lines_loop(text, text_len, start, line, acc):
    while True:
        if (start >= text_len):
            return intern_node(FSC_REPO_TEXT_LINES, reverse(([fsc_repo_text_line(0, 0, 1, 0, 1, 0), *acc] if (text_len == 0) else acc)))
        else:
            end = fsc_line_end(text, start)
            next = fsc_line_next(text, start)
            text, text_len, start, line, acc = text, text_len, next, (line + 1), [fsc_repo_text_line(start, (end - start), line, 0, line, (end - start)), *acc]
            continue

def fsc_repo_text_lines(text):
    return fsc_repo_text_lines_loop(text, str_len(text), 0, 1, empty())

def fsc_repo_empty_spans():
    return intern_node(FSC_REPO_TEXT_LINES, empty())

def fsc_repo_document(kind, size, structure, spans):
    return intern_node(FSC_REPO_DOCUMENT, [kind, intern_trivial_int(size), structure, spans])

def fsc_repo_text_document(kind, text, structure):
    lines = fsc_repo_text_lines(text)
    return fsc_repo_document(kind, str_len(text), structure, lines)

def fsc_repo_binary_document(kind, bytes, structure):
    return fsc_repo_document(kind, len(bytes), structure, fsc_repo_empty_spans())

def fsc_repo_document_kind(document):
    return node_children(document)[0]

def fsc_repo_document_size(document):
    return node_value(node_children(document)[1])

def fsc_repo_document_structure(document):
    return node_children(document)[2]

def fsc_repo_document_spans(document):
    return node_children(document)[3]

def fsc_repo_text_document_line_count(document):
    return len(node_children(fsc_repo_document_spans(document)))

def fsc_repo_text_document_lines(document):
    return fsc_repo_document_spans(document)

def fsc_repo_text_document_structure(document):
    return fsc_repo_document_structure(document)

def fsc_repo_text_line_number(line):
    if (len(line) > 0):
        return line[3]
    else:
        return node_value(node_children(line)[2])

def fsc_repo_text_line_start(line):
    if (len(line) > 0):
        return line[1]
    else:
        return node_value(node_children(line)[0])

def fsc_repo_text_line_length(line):
    if (len(line) > 0):
        return line[2]
    else:
        return node_value(node_children(line)[1])

def fsc_repo_text_line_end(line):
    return (fsc_repo_text_line_start(line) + fsc_repo_text_line_length(line))

def fsc_repo_text_line_start_col(line):
    if (len(line) > 0):
        return line[4]
    else:
        return node_value(node_children(line)[3])

def fsc_repo_text_line_end_line(line):
    if (len(line) > 0):
        return line[5]
    else:
        return node_value(node_children(line)[4])

def fsc_repo_text_line_end_col(line):
    if (len(line) > 0):
        return line[6]
    else:
        return node_value(node_children(line)[5])

def fsc_repo_binary_document_byte_count(document):
    return fsc_repo_document_size(document)

def fsc_repo_binary_document_structure(document):
    return fsc_repo_document_structure(document)

def fsc_repo_corpus(name, files):
    return compiler_object('fsc-repo-corpus', [name, files], files, compiler_identity_inverse)

def fsc_repo_corpus_name(corpus):
    return compiler_object_value(corpus)[0]

def fsc_repo_corpus_files(corpus):
    return compiler_object_value(corpus)[1]

def fsc_repo_corpus_total_bytes(files):
    if is_nil(files):
        return 0
    else:
        return (fsc_repo_file_byte_count(files[0]) + fsc_repo_corpus_total_bytes(files[1:]))

def fsc_bmf_lower_node(rule, source_stream):
    match = apply_object_rule(rule, source_stream)
    object = cap_get(match_caps(match), 'result')
    return bmf_object_value(object)

def is_fsc_bmf_source_node_eq(rule, source_stream, node):
    return node_eq(fsc_bmf_lower_node(rule, source_stream), node)

def is_fsc_bmf_roundtrip_node_eq(rule, source_stream):
    return is_bmf_roundtrip_node_eq(bmf_roundtrip(rule, source_stream))

def is_fsc_lens_roundtrip_node_eq(roundtrip, node):
    return node_eq(bmf_lens_roundtrip_node(roundtrip), node)

def is_fsc_lens_roundtrip_anchor_eq(roundtrip, anchor):
    return str_eq(bmf_lens_roundtrip_anchor(roundtrip), anchor)

def form_source_compile_loop(src, i):
    pos = fsc_find_string_from(src, 'section [', i)
    return (fsc_sub(src, i, str_len(src)) if (pos < 0) else ((dialect_start := (pos + 9)), (dialect_end := fsc_find_char_from(src, ']', dialect_start)), (open := fsc_find_char_from(src, '{', dialect_end)), (close := fsc_section_end(src, (open + 1))), (dialect_name := fsc_sub(src, dialect_start, dialect_end)), (body := fsc_sub(src, (open + 1), close)), str_concat(fsc_sub(src, i, pos), str_concat(fsc_compile_section(dialect_name, body), form_source_compile_loop(src, fsc_line_next(src, close)))))[-1])

def form_source_compile_text(src):
    return form_source_compile_loop(src, 0)

def fsc_string_to_bytes_len_loop(s, s_len, i):
    if (i >= s_len):
        return empty()
    else:
        return [ord(char_at(s, i)), *fsc_string_to_bytes_len_loop(s, s_len, (i + 1))]

def fsc_string_to_bytes(s):
    return fsc_string_to_bytes_len_loop(s, str_len(s), 0)

def form_source_compile_file(in_path, out_path):
    src = read_file(in_path)
    compiled = form_source_compile_text(src)
    return write_file_text(out_path, compiled)

FSC_ACTION_BLOCK_DO = make_nodeid(1, 2, 9, 1)
FSC_ACTION_BLOCK_SEQ = make_nodeid(1, 2, 9, 2)
FSC_ACTION_BLOCK_LET = make_nodeid(1, 2, 9, 3)
FSC_ACTION_MATH_ADD = make_nodeid(1, 2, 12, 1)
FSC_ACTION_MATH_SUB = make_nodeid(1, 2, 12, 2)
FSC_ACTION_MATH_MUL = make_nodeid(1, 2, 12, 3)
FSC_ACTION_MATH_MOD = make_nodeid(1, 2, 12, 5)
FSC_ACTION_COMPARE_EQ = make_nodeid(1, 2, 13, 1)
FSC_ACTION_COMPARE_LT = make_nodeid(1, 2, 13, 3)
FSC_ACTION_COMPARE_LE = make_nodeid(1, 2, 13, 4)
FSC_ACTION_COMPARE_GT = make_nodeid(1, 2, 13, 5)
FSC_ACTION_COMPARE_GE = make_nodeid(1, 2, 13, 6)
FSC_ACTION_COND_IF = make_nodeid(1, 2, 11, 2)
FSC_ACTION_FNDEF = make_nodeid(1, 2, 31, 1)
FSC_ACTION_FNCALL = make_nodeid(1, 2, 32, 1)
FSC_ACTION_IDENT = make_nodeid(1, 2, 33, 1)
fsc_action_keywords = ['def', 'let', 'if', 'then', 'else', 'do']
fsc_common_op2 = ['==', '!=', '<=', '>=', '->', '=>', ':=', '+=', '-=', '*=', '/=', '**', '//', '<<', '>>', '<-', '?.']
fsc_action_source_dialect = fsc_source_dialect(fsc_action_keywords, 'form-action-keyword', 'form-action-name', 'form-action-int', 'form-action-string', 'form-action-op', 'form-action-eof', fsc_common_op2)
FSC_REPO_DOCUMENT = make_nodeid(8, 45, 6, 10)
FSC_REPO_TEXT_LINES = make_nodeid(8, 45, 6, 11)
FSC_REPO_TEXT_LINE = make_nodeid(8, 45, 6, 12)
FSC_REPO_MEANING = make_nodeid(8, 45, 6, 13)
FSC_REPO_MEANING_FIELD = make_nodeid(8, 45, 6, 14)

if __name__ == '__main__':
    pass
