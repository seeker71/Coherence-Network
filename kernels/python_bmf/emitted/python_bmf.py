"""Emitted from Form source by kernels/python_bmf/emit_python.py."""
from kernels.python_bmf.host_primitives import *  # noqa: F401, F403

def py_keyword(value):
    return bmf_atom('py-keyword', value)

def py_name(value):
    return bmf_atom('py-name', value)

def py_op(value):
    return bmf_atom('py-op', value)

def py_int(value):
    return bmf_atom('py-int', value)

def py_float(value):
    return bmf_atom('py-float', value)

def py_string(value):
    return bmf_atom('py-string', value)

def py_bytes(value):
    return bmf_atom('py-bytes', value)

def py_fstring(value):
    return bmf_atom('py-fstring', value)

def py_tstring(value):
    return bmf_atom('py-tstring', value)

def py_layout(value):
    return bmf_atom('py-layout', value)

def python_source_dialect(_unused):
    return fsc_source_dialect(python_source_keywords, 'py-keyword', 'py-name', 'py-int', 'py-string', 'py-op', 'py-eof', python_source_ops)

def is_python_source_quote(ch):
    return (str_eq(ch, '"') or str_eq(ch, "'"))

def is_python_source_string_prefix(ch):
    return (str_eq(ch, 'r') or (str_eq(ch, 'R') or (str_eq(ch, 'b') or (str_eq(ch, 'B') or (str_eq(ch, 'f') or (str_eq(ch, 'F') or (str_eq(ch, 't') or (str_eq(ch, 'T') or (str_eq(ch, 'u') or str_eq(ch, 'U'))))))))))

def is_python_source_prefix_has(prefix, low, up):
    return (is_fsc_contains(prefix, low) or is_fsc_contains(prefix, up))

def python_source_prefix_string_kind(prefix):
    if is_python_source_prefix_has(prefix, 'f', 'F'):
        return 'py-fstring'
    else:
        if is_python_source_prefix_has(prefix, 't', 'T'):
            return 'py-tstring'
        else:
            if is_python_source_prefix_has(prefix, 'b', 'B'):
                return 'py-bytes'
            else:
                return 'py-string'

def python_source_skip_comment(cursor):
    if is_fsc_source_cursor_end(cursor):
        return cursor
    else:
        if str_eq(fsc_source_cursor_char(cursor), '\n'):
            return fsc_source_cursor_advance(cursor)
        else:
            return python_source_skip_comment(fsc_source_cursor_advance(cursor))

def python_source_scan_skip(cursor):
    if is_fsc_source_cursor_end(cursor):
        return cursor
    else:
        if is_fsc_space(fsc_source_cursor_char(cursor)):
            return python_source_scan_skip(fsc_source_cursor_advance(cursor))
        else:
            if str_eq(fsc_source_cursor_char(cursor), '#'):
                return python_source_scan_skip(python_source_skip_comment(cursor))
            else:
                return cursor

def python_source_scan_string_loop(cursor, quote, value):
    if is_fsc_source_cursor_end(cursor):
        return [value, cursor]
    else:
        if str_eq(fsc_source_cursor_char(cursor), '\\'):
            return python_source_scan_string_loop(fsc_source_cursor_advance(fsc_source_cursor_advance(cursor)), quote, str_concat(value, fsc_source_cursor_char(fsc_source_cursor_advance(cursor))))
        else:
            if str_eq(fsc_source_cursor_char(cursor), quote):
                return [value, fsc_source_cursor_advance(cursor)]
            else:
                return python_source_scan_string_loop(fsc_source_cursor_advance(cursor), quote, str_concat(value, fsc_source_cursor_char(cursor)))

def python_source_scan_triple_string_loop(cursor, quote, value):
    if is_fsc_source_cursor_end(cursor):
        return [value, cursor]
    else:
        if (is_fsc_source_cursor_prefix(cursor, quote) and (is_fsc_source_cursor_prefix(fsc_source_cursor_advance(cursor), quote) and is_fsc_source_cursor_prefix(fsc_source_cursor_advance(fsc_source_cursor_advance(cursor)), quote))):
            return [value, fsc_source_advance_n(cursor, 3)]
        else:
            return python_source_scan_triple_string_loop(fsc_source_cursor_advance(cursor), quote, str_concat(value, fsc_source_cursor_char(cursor)))

def python_source_scan_string_at(start, quote, string_kind):
    open_quote = fsc_source_cursor_char(start)
    return (((body_start := fsc_source_advance_n(start, 3)), (read := python_source_scan_triple_string_loop(body_start, open_quote, '')), fsc_scan_result(fsc_source_object(string_kind, read[0], start, read[1]), read[1]))[-1] if (is_fsc_source_cursor_prefix(start, open_quote) and (is_fsc_source_cursor_prefix(fsc_source_cursor_advance(start), open_quote) and is_fsc_source_cursor_prefix(fsc_source_cursor_advance(fsc_source_cursor_advance(start)), open_quote))) else ((body_start := fsc_source_cursor_advance(start)), (fsc_scan_result(fsc_source_object(string_kind, '', start, fsc_source_cursor_advance(body_start)), fsc_source_cursor_advance(body_start)) if str_eq(fsc_source_cursor_char(body_start), open_quote) else ((read := python_source_scan_string_loop(body_start, open_quote, '')), fsc_scan_result(fsc_source_object(string_kind, read[0], start, read[1]), read[1]))[-1]))[-1])

def python_source_prefixed_string_prefix_len(cursor):
    ch = fsc_source_cursor_char(cursor)
    next = fsc_source_cursor_char(fsc_source_cursor_advance(cursor))
    after_next = fsc_source_cursor_char(fsc_source_advance_n(cursor, 2))
    return (2 if (is_python_source_string_prefix(ch) and (is_python_source_string_prefix(next) and is_python_source_quote(after_next))) else (1 if (is_python_source_string_prefix(ch) and is_python_source_quote(next)) else 0))

def python_source_scan_prefixed_string(start, prefix_len):
    prefix = (str_concat(fsc_source_cursor_char(start), fsc_source_cursor_char(fsc_source_cursor_advance(start))) if (prefix_len == 2) else fsc_source_cursor_char(start))
    quote_start = fsc_source_advance_n(start, prefix_len)
    return python_source_scan_string_at(quote_start, fsc_source_cursor_char(quote_start), python_source_prefix_string_kind(prefix))

def is_python_source_prefixed_string_start(cursor):
    return (python_source_prefixed_string_prefix_len(cursor) > 0)

def is_python_source_int_char(ch):
    return (is_fsc_digit(ch) or str_eq(ch, '_'))

def python_source_scan_int_loop(cursor, value):
    if is_fsc_source_cursor_end(cursor):
        return [value, cursor]
    else:
        ch = fsc_source_cursor_char(cursor)
        return (python_source_scan_int_loop(fsc_source_cursor_advance(cursor), str_concat(value, ch)) if is_python_source_int_char(ch) else [value, cursor])

def python_source_scan_int(start):
    read = python_source_scan_int_loop(start, '')
    return fsc_scan_result(fsc_source_object('py-int', read[0], start, read[1]), read[1])

def python_source_scan_next(cursor):
    start = python_source_scan_skip(cursor)
    ch = fsc_source_cursor_char(start)
    prefix_len = python_source_prefixed_string_prefix_len(start)
    return (fsc_scan_result(fsc_source_object('py-eof', '', start, start), start) if is_fsc_source_cursor_end(start) else (python_source_scan_prefixed_string(start, prefix_len) if (prefix_len > 0) else (python_source_scan_string_at(start, ch, 'py-string') if is_python_source_quote(ch) else (python_source_scan_int(start) if is_fsc_digit(ch) else (fsc_source_scan_name(start, python_source_keywords, 'py-keyword', 'py-name') if is_fsc_source_name_start_char(ch) else fsc_source_scan_op(start, 'py-op', python_source_ops))))))

def python_source_scan_text_loop(cursor, acc):
    result = python_source_scan_next(cursor)
    object = fsc_scan_result_object(result)
    return (reverse_list(acc) if str_eq(bmf_object_kind(object), 'py-eof') else python_source_scan_text_loop(fsc_scan_result_cursor(result), [object, *acc]))

def python_source_scan_text(source):
    return python_source_scan_text_loop(fsc_source_cursor(source, 0, 1, 0), empty())

def python_source_scan_file(path):
    return python_source_scan_text_loop(fsc_file_source_cursor(path, 0, 1, 0, file_size(path)), empty())

def py_newline():
    return py_layout('NEWLINE')

def py_indent():
    return py_layout('INDENT')

def py_dedent():
    return py_layout('DEDENT')

def py_endmarker():
    return py_layout('ENDMARKER')

def python_layout_dedents(from_indent, to_indent, acc):
    if (from_indent <= to_indent):
        return acc
    else:
        return python_layout_dedents((from_indent - 4), to_indent, [py_dedent(), *acc])

def python_layout_shift(prev_indent, next_indent, acc):
    if (next_indent > prev_indent):
        return [py_indent(), *acc]
    else:
        if (next_indent < prev_indent):
            return python_layout_dedents(prev_indent, next_indent, acc)
        else:
            return acc

def python_source_layout_loop(objects, prev_line, prev_indent, is_current_line_start, acc):
    if is_nil(objects):
        return reverse_list([py_endmarker(), *python_layout_dedents(prev_indent, 0, acc)])
    else:
        object = objects[0]
        line = python_source_object_line(object)
        col = python_source_object_col(object)
        is_new_line = (line > prev_line)
        with_newline = ([py_newline(), *acc] if is_new_line else acc)
        with_layout = (python_layout_shift(prev_indent, col, with_newline) if is_new_line else with_newline)
        return python_source_layout_loop(objects[1:], line, (col if is_new_line else prev_indent), False, [object, *with_layout])

def python_source_layout_objects(objects):
    return python_source_layout_loop(objects, 1, 0, True, empty())

def python_source_scan_text_with_layout(source):
    return python_source_layout_objects(python_source_scan_text(source))

def python_source_scan_file_with_layout(path):
    return python_source_layout_objects(python_source_scan_file(path))

def python_source_object_span(object):
    return bmf_object_source_span(object)[0]

def python_source_object_line(object):
    return fsc_repo_text_line_number(python_source_object_span(object))

def python_source_object_col(object):
    return fsc_repo_text_line_start_col(python_source_object_span(object))

def is_python_source_open_group(object):
    return (str_eq(bmf_object_kind(object), 'py-op') and (str_eq(bmf_object_value(object), '(') or (str_eq(bmf_object_value(object), '[') or str_eq(bmf_object_value(object), '{'))))

def is_python_source_close_group(object):
    return (str_eq(bmf_object_kind(object), 'py-op') and (str_eq(bmf_object_value(object), ')') or (str_eq(bmf_object_value(object), ']') or str_eq(bmf_object_value(object), '}'))))

def python_source_depth_after(depth, object):
    if is_python_source_open_group(object):
        return (depth + 1)
    else:
        if is_python_source_close_group(object):
            if (depth > 0):
                return (depth - 1)
            else:
                return 0
        else:
            return depth

def python_statement_kind_from_first(object):
    if str_eq(bmf_object_kind(object), 'py-keyword'):
        return bmf_object_value(object)
    else:
        if (str_eq(bmf_object_kind(object), 'py-op') and str_eq(bmf_object_value(object), '@')):
            return 'decorator'
        else:
            return 'expr'

def python_statement_kind(objects):
    if is_nil(objects):
        return 'empty'
    else:
        return python_statement_kind_from_first(objects[0])

def python_statement_indent(objects):
    if is_nil(objects):
        return 0
    else:
        return python_source_object_col(objects[0])

def python_parse_statement(objects):
    return bmf_object('py-statement', [python_statement_kind(objects), python_statement_indent(objects), python_statement_cpython_rule_from_tokens(objects), len(objects)], bmf_collection(objects), bmf_identity_inverse)

def python_statement_kind_value(statement):
    return bmf_object_value(statement)[0]

def python_statement_indent_value(statement):
    return bmf_object_value(statement)[1]

def python_statement_tokens(statement):
    return bmf_collection_items(bmf_object_source(statement))

def is_python_token_value(object, value):
    return str_eq(bmf_object_value(object), value)

def is_python_statement_token_value(tokens, index, value):
    return ((len(tokens) > index) and is_python_token_value(tokens[index], value))

def python_statement_cpython_rule_from_tokens(tokens):
    if is_nil(tokens):
        return 'empty'
    else:
        if is_python_statement_token_value(tokens, 0, 'from'):
            return 'import_stmt'
        else:
            if is_python_statement_token_value(tokens, 0, 'import'):
                return 'import_stmt'
            else:
                if is_python_statement_token_value(tokens, 0, 'return'):
                    return 'return_stmt'
                else:
                    if is_python_statement_token_value(tokens, 0, 'raise'):
                        return 'raise_stmt'
                    else:
                        if is_python_statement_token_value(tokens, 0, 'pass'):
                            return 'pass_stmt'
                        else:
                            if is_python_statement_token_value(tokens, 0, 'del'):
                                return 'del_stmt'
                            else:
                                if is_python_statement_token_value(tokens, 0, 'yield'):
                                    return 'yield_stmt'
                                else:
                                    if is_python_statement_token_value(tokens, 0, 'assert'):
                                        return 'assert_stmt'
                                    else:
                                        if is_python_statement_token_value(tokens, 0, 'break'):
                                            return 'break_stmt'
                                        else:
                                            if is_python_statement_token_value(tokens, 0, 'continue'):
                                                return 'continue_stmt'
                                            else:
                                                if is_python_statement_token_value(tokens, 0, 'global'):
                                                    return 'global_stmt'
                                                else:
                                                    if is_python_statement_token_value(tokens, 0, 'nonlocal'):
                                                        return 'nonlocal_stmt'
                                                    else:
                                                        if is_python_statement_token_value(tokens, 0, 'class'):
                                                            return 'class_def'
                                                        else:
                                                            if is_python_statement_token_value(tokens, 0, 'def'):
                                                                return 'function_def'
                                                            else:
                                                                if (is_python_statement_token_value(tokens, 0, 'async') and is_python_statement_token_value(tokens, 1, 'def')):
                                                                    return 'function_def'
                                                                else:
                                                                    if is_python_statement_token_value(tokens, 0, 'if'):
                                                                        return 'if_stmt'
                                                                    else:
                                                                        if is_python_statement_token_value(tokens, 0, 'while'):
                                                                            return 'while_stmt'
                                                                        else:
                                                                            if (is_python_statement_token_value(tokens, 0, 'for') or (is_python_statement_token_value(tokens, 0, 'async') and is_python_statement_token_value(tokens, 1, 'for'))):
                                                                                return 'for_stmt'
                                                                            else:
                                                                                if (is_python_statement_token_value(tokens, 0, 'with') or (is_python_statement_token_value(tokens, 0, 'async') and is_python_statement_token_value(tokens, 1, 'with'))):
                                                                                    return 'with_stmt'
                                                                                else:
                                                                                    if is_python_statement_token_value(tokens, 0, 'try'):
                                                                                        return 'try_stmt'
                                                                                    else:
                                                                                        if is_python_statement_token_value(tokens, 0, 'match'):
                                                                                            return 'match_stmt'
                                                                                        else:
                                                                                            if is_python_statement_token_value(tokens, 0, 'type'):
                                                                                                return 'type_alias'
                                                                                            else:
                                                                                                if is_python_statement_token_value(tokens, 1, '='):
                                                                                                    return 'assignment'
                                                                                                else:
                                                                                                    if is_python_statement_token_value(tokens, 1, ':='):
                                                                                                        return 'assignment_expression'
                                                                                                    else:
                                                                                                        return 'star_expressions'

def python_statement_cpython_rule(statement):
    return bmf_object_value(statement)[2]

def python_statement_token_count(statement):
    return bmf_object_value(statement)[3]

def python_parse_module_object(statements, source_objects):
    return bmf_object('py-module', bmf_collection(statements), bmf_empty(0), bmf_identity_inverse)

def python_module_statements(module):
    return bmf_collection_items(bmf_object_value(module))

def python_module_source_objects_loop(statements, acc):
    if is_nil(statements):
        return reverse_list(acc)
    else:
        return python_module_source_objects_loop(statements[1:], append(reverse_list(python_statement_tokens(statements[0])), acc))

def python_module_source_objects(module):
    return python_module_source_objects_loop(python_module_statements(module), empty())

def python_statement_tree(statement, children):
    return bmf_object('py-statement-tree', [python_statement_kind_value(statement), python_statement_indent_value(statement), python_statement_cpython_rule(statement), python_statement_token_count(statement), bmf_collection(children)], bmf_object_source(statement), bmf_identity_inverse)

def python_statement_tree_kind(tree):
    return bmf_object_value(tree)[0]

def python_statement_tree_indent(tree):
    return bmf_object_value(tree)[1]

def python_statement_tree_tokens(tree):
    return bmf_collection_items(bmf_object_source(tree))

def python_statement_tree_children(tree):
    return bmf_collection_items(bmf_object_value(tree)[4])

def python_statement_tree_cpython_rule(tree):
    return bmf_object_value(tree)[2]

def python_statement_tree_token_count(tree):
    return bmf_object_value(tree)[3]

def python_parse_block_result(trees, rest):
    return ['python-parse-block-result', trees, rest]

def python_parse_block_result_trees(result):
    return result[1]

def python_parse_block_result_rest(result):
    return result[2]

def python_parse_statement_trees_loop(statements, indent, acc):
    if is_nil(statements):
        return python_parse_block_result(reverse_list(acc), empty())
    else:
        statement = statements[0]
        statement_indent = python_statement_indent_value(statement)
        return (python_parse_block_result(reverse_list(acc), statements) if (statement_indent < indent) else (python_parse_block_result(reverse_list(acc), statements) if (statement_indent > indent) else ((rest := statements[1:]), (child_result := (python_parse_statement_trees_loop(rest, python_statement_indent_value(rest[0]), empty()) if ((not is_nil(rest)) and (python_statement_indent_value(rest[0]) > statement_indent)) else python_parse_block_result(empty(), rest))), (tree := python_statement_tree(statement, python_parse_block_result_trees(child_result))), python_parse_statement_trees_loop(python_parse_block_result_rest(child_result), indent, [tree, *acc]))[-1]))

def python_parse_statement_trees(statements):
    return python_parse_block_result_trees(python_parse_statement_trees_loop(statements, 0, empty()))

def python_parse_module_tree_object(module):
    return bmf_object('py-module-tree', bmf_collection(python_parse_statement_trees(python_module_statements(module))), bmf_object_source(module), bmf_identity_inverse)

def python_module_tree_statements(module_tree):
    return bmf_collection_items(bmf_object_value(module_tree))

def python_parse_module_tree_file(path):
    return python_parse_module_tree_object(python_parse_module_file(path))

def python_parse_module_finish(current, statements, source_objects):
    return python_parse_module_object(reverse_list((statements if is_nil(current) else [python_parse_statement(reverse_list(current)), *statements])), source_objects)

def python_parse_module_loop(remaining, current, current_line, depth, statements, source_objects):
    if is_nil(remaining):
        return python_parse_module_finish(current, statements, source_objects)
    else:
        object = remaining[0]
        line = python_source_object_line(object)
        next_depth = python_source_depth_after(depth, object)
        return (python_parse_module_loop(remaining[1:], [object], line, next_depth, statements, source_objects) if is_nil(current) else (python_parse_module_loop(remaining[1:], [object], line, next_depth, [python_parse_statement(reverse_list(current)), *statements], source_objects) if ((line > current_line) and (depth == 0)) else python_parse_module_loop(remaining[1:], [object, *current], line, next_depth, statements, source_objects)))

def python_parse_module_objects(source_objects):
    return python_parse_module_loop(source_objects, empty(), 0, 0, empty(), source_objects)

def python_parse_module_text(source):
    return python_parse_module_objects(python_source_scan_text(source))

def python_parse_module_file(path):
    return python_parse_module_objects(python_source_scan_file(path))

def kw(value):
    return object_lit('py-keyword', value)

def op(value):
    return object_lit('py-op', value)

def name(capture_name):
    return ['capture', capture_name, object_lit('py-name', '')]

def int_lit(capture_name):
    return ['capture', capture_name, object_lit('py-int', '')]

def float_lit(capture_name):
    return ['capture', capture_name, object_lit('py-float', '')]

def string_lit(capture_name):
    return ['capture', capture_name, object_lit('py-string', '')]

def bytes_lit(capture_name):
    return ['capture', capture_name, object_lit('py-bytes', '')]

def fstring_lit(capture_name):
    return ['capture', capture_name, object_lit('py-fstring', '')]

def tstring_lit(capture_name):
    return ['capture', capture_name, object_lit('py-tstring', '')]

def python_kw(value):
    return kw(value)

def python_op(value):
    return op(value)

def python_name(capture_name):
    return name(capture_name)

def python_int_lit(capture_name):
    return int_lit(capture_name)

def python_float_lit(capture_name):
    return float_lit(capture_name)

def python_string_lit(capture_name):
    return string_lit(capture_name)

def python_bytes_lit(capture_name):
    return bytes_lit(capture_name)

def python_fstring_lit(capture_name):
    return fstring_lit(capture_name)

def python_tstring_lit(capture_name):
    return tstring_lit(capture_name)

def pybmf_value(objects, capture_name):
    return bmf_collection_value(objects, capture_name)

def pybmf_trivial_string(objects, capture_name):
    return intern_trivial_string(pybmf_value(objects, capture_name))

def pybmf_trivial_int(objects, capture_name):
    return intern_trivial_int(str_to_int(pybmf_value(objects, capture_name)))

def pybmf_empty_string(_objects):
    return intern_trivial_string('')

def pybmf_node_kids(object):
    return node_children(bmf_object_value(object))

def pybmf_emit_import(objects):
    return intern_node(PY_BMF_IMPORT, [pybmf_trivial_string(objects, 'module'), pybmf_trivial_string(objects, 'alias')])

def pybmf_emit_import_bare(objects):
    return intern_node(PY_BMF_IMPORT, [pybmf_trivial_string(objects, 'module'), pybmf_empty_string(objects)])

def pybmf_source_import_as(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('import'), py_name(node_value(kids[0])), py_keyword('as'), py_name(node_value(kids[1]))]

def pybmf_emit_from_import(objects):
    return intern_node(PY_BMF_FROM_IMPORT, [pybmf_trivial_string(objects, 'module'), pybmf_trivial_string(objects, 'name')])

def pybmf_source_from_import(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('from'), py_name(node_value(kids[0])), py_keyword('import'), py_name(node_value(kids[1]))]

def pybmf_emit_def(objects):
    return intern_node(PY_BMF_DEF, [pybmf_trivial_string(objects, 'name')])

def pybmf_source_def(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('def'), py_name(node_value(kids[0])), py_op('('), py_op(')'), py_op(':')]

def pybmf_emit_def2(objects):
    return intern_node(PY_BMF_DEF, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b')])

def pybmf_source_def2(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('def'), py_name(node_value(kids[0])), py_op('('), py_name(node_value(kids[1])), py_op(','), py_name(node_value(kids[2])), py_op(')'), py_op(':')]

def pybmf_emit_class(objects):
    return intern_node(PY_BMF_CLASS, [pybmf_trivial_string(objects, 'name')])

def pybmf_source_class(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('class'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass')]

def pybmf_emit_assign_ident(objects):
    return intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_assign_ident(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('='), py_name(node_value(kids[1]))]

def pybmf_emit_assign_int(objects):
    return intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_int(objects, 'value')])

def pybmf_source_assign_int(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('='), py_int(int_to_str(node_value(kids[1:][0])))]

def pybmf_emit_return_ident(objects):
    return intern_node(PY_BMF_RETURN, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_return_ident(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('return'), py_name(node_value(kids[0]))]

def pybmf_emit_return_int(objects):
    return intern_node(PY_BMF_RETURN, [pybmf_trivial_int(objects, 'value')])

def pybmf_source_return_int(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('return'), py_int(int_to_str(node_value(kids[0])))]

def pybmf_emit_return_plus_ident(objects):
    return intern_node(PY_BMF_RETURN, [intern_node(PY_BMF_BINOP, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('+'), pybmf_trivial_string(objects, 'right')])])

def pybmf_source_return_plus_ident(object):
    kids = pybmf_node_kids(object)
    binop = kids[0]
    binop_kids = node_children(binop)
    return [py_keyword('return'), py_name(node_value(binop_kids[0])), py_op('+'), py_name(node_value(binop_kids[2]))]

def pybmf_emit_raise(objects):
    return intern_node(PY_BMF_RAISE, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_raise(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('raise'), py_name(node_value(kids[0]))]

def pybmf_emit_pass(_objects):
    return intern_node(PY_BMF_PASS, empty())

def pybmf_emit_if(objects):
    return intern_node(PY_BMF_IF, [pybmf_trivial_string(objects, 'cond')])

def pybmf_source_if_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('if'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass')]

def pybmf_emit_while(objects):
    return intern_node(PY_BMF_WHILE, [pybmf_trivial_string(objects, 'cond')])

def pybmf_source_while_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('while'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass')]

def pybmf_emit_for(objects):
    return intern_node(PY_BMF_FOR, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'iter')])

def pybmf_source_for_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('for'), py_name(node_value(kids[0])), py_keyword('in'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_call0(objects):
    return intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'callee')])

def pybmf_source_call0(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('('), py_op(')')]

def pybmf_emit_call1_ident(objects):
    return intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'callee'), pybmf_trivial_string(objects, 'arg')])

def pybmf_source_call1_ident(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('('), py_name(node_value(kids[1])), py_op(')')]

def pybmf_emit_assign_call2_ident(objects):
    return intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'target'), intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'callee'), pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b')])])

def pybmf_emit_int(objects):
    return intern_node(PY_BMF_INT, [pybmf_trivial_int(objects, 'value')])

def pybmf_emit_string(objects):
    return intern_node(PY_BMF_STRING, [pybmf_trivial_string(objects, 'value')])

def pybmf_emit_ident(objects):
    return intern_node(PY_BMF_IDENT, [pybmf_trivial_string(objects, 'value')])

def pybmf_emit_attr(objects):
    return intern_node(PY_BMF_ATTR, [pybmf_trivial_string(objects, 'object'), pybmf_trivial_string(objects, 'field')])

def pybmf_source_attr(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('.'), py_name(node_value(kids[1]))]

def pybmf_emit_method_call0(objects):
    return intern_node(PY_BMF_METHOD_CALL, [pybmf_trivial_string(objects, 'object'), pybmf_trivial_string(objects, 'method')])

def pybmf_source_method_call0(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('.'), py_name(node_value(kids[1])), py_op('('), py_op(')')]

def pybmf_emit_list3_int(objects):
    return intern_node(PY_BMF_LIST, [pybmf_trivial_int(objects, 'a'), pybmf_trivial_int(objects, 'b'), pybmf_trivial_int(objects, 'c')])

def pybmf_emit_dict1_ident_int(objects):
    return intern_node(PY_BMF_DICT, [pybmf_trivial_string(objects, 'key'), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_annotated_assign_int(objects):
    return intern_node(PY_BMF_ANNOTATED, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'type'), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_aug_assign_int(objects):
    return intern_node(PY_BMF_AUG_ASSIGN, [pybmf_trivial_string(objects, 'target'), intern_trivial_string('+='), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_sample_module(objects):
    return intern_node(PY_BMF_MODULE, [pybmf_trivial_string(objects, 'import_a'), pybmf_trivial_string(objects, 'import_b'), pybmf_trivial_string(objects, 'from_mod'), pybmf_trivial_string(objects, 'from_name'), pybmf_trivial_string(objects, 'const_name'), pybmf_trivial_int(objects, 'const_value'), pybmf_trivial_string(objects, 'add_name'), pybmf_trivial_string(objects, 'add_a'), pybmf_trivial_string(objects, 'add_b'), intern_node(PY_BMF_RETURN, [intern_node(PY_BMF_BINOP, [pybmf_trivial_string(objects, 'ret_left'), intern_trivial_string('+'), pybmf_trivial_string(objects, 'ret_right')])]), pybmf_trivial_string(objects, 'main_name'), intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'x_name'), pybmf_trivial_int(objects, 'x_value')]), intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'y_name'), pybmf_trivial_int(objects, 'y_value')]), intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'z_name'), intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'z_call'), pybmf_trivial_string(objects, 'z_arg_a'), pybmf_trivial_string(objects, 'z_arg_b')])]), intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'print_call'), pybmf_trivial_string(objects, 'print_arg')])])

def pybmf_emit_assign_string(objects):
    return intern_node(PY_BMF_ASSIGN, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_assign_string(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('='), py_string(node_value(kids[1]))]

def pybmf_emit_return_string(objects):
    return intern_node(PY_BMF_RETURN, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_return_string(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('return'), py_string(node_value(kids[0]))]

def pybmf_emit_bool_true(_objects):
    return intern_node(PY_BMF_BOOL, [intern_trivial_string('True')])

def pybmf_emit_bool_false(_objects):
    return intern_node(PY_BMF_BOOL, [intern_trivial_string('False')])

def pybmf_emit_none(_objects):
    return intern_node(PY_BMF_NONE, empty())

def pybmf_emit_unary_not(objects):
    return intern_node(PY_BMF_UNARY, [intern_trivial_string('not'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_unary_not(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('not'), py_name(node_value(kids[1]))]

def pybmf_emit_unary_neg_int(objects):
    return intern_node(PY_BMF_UNARY, [intern_trivial_string('-'), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_unary_plus_int(objects):
    return intern_node(PY_BMF_UNARY, [intern_trivial_string('+'), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_unary_invert(objects):
    return intern_node(PY_BMF_UNARY, [intern_trivial_string('~'), pybmf_trivial_string(objects, 'value')])

def pybmf_emit_compare_eq(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('=='), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_lt(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('<'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_ne(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('!='), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_gt(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('>'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_gte(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('>='), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_lte(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('<='), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_in(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('in'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_not_in(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('not in'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_is(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('is'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_compare_is_not(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('is not'), pybmf_trivial_string(objects, 'right')])

def pybmf_source_compare_op(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op(node_value(kids[1])), py_name(node_value(kids[2]))]

def pybmf_source_compare_word(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_keyword(node_value(kids[1])), py_name(node_value(kids[2]))]

def pybmf_source_compare_not_in(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_keyword('not'), py_keyword('in'), py_name(node_value(kids[2]))]

def pybmf_source_compare_is_not(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_keyword('is'), py_keyword('not'), py_name(node_value(kids[2]))]

def pybmf_emit_compare_chain_lt_lte(objects):
    return intern_node(PY_BMF_COMPARE, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('<'), pybmf_trivial_string(objects, 'middle'), intern_trivial_string('<='), pybmf_trivial_string(objects, 'right')])

def pybmf_source_compare_chain(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op(node_value(kids[1])), py_name(node_value(kids[2])), py_op(node_value(kids[3])), py_name(node_value(kids[4]))]

def pybmf_emit_binop(objects, op):
    return intern_node(PY_BMF_BINOP, [pybmf_trivial_string(objects, 'left'), intern_trivial_string(op), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_binop_sub(objects):
    return pybmf_emit_binop(objects, '-')

def pybmf_emit_binop_mul(objects):
    return pybmf_emit_binop(objects, '*')

def pybmf_emit_binop_div(objects):
    return pybmf_emit_binop(objects, '/')

def pybmf_emit_binop_mod(objects):
    return pybmf_emit_binop(objects, '%')

def pybmf_emit_binop_pow(objects):
    return pybmf_emit_binop(objects, '**')

def pybmf_emit_binop_floor_div(objects):
    return pybmf_emit_binop(objects, '//')

def pybmf_emit_binop_bit_or(objects):
    return pybmf_emit_binop(objects, '|')

def pybmf_emit_binop_bit_and(objects):
    return pybmf_emit_binop(objects, '&')

def pybmf_emit_binop_bit_xor(objects):
    return pybmf_emit_binop(objects, '^')

def pybmf_emit_binop_lshift(objects):
    return pybmf_emit_binop(objects, '<<')

def pybmf_emit_binop_rshift(objects):
    return pybmf_emit_binop(objects, '>>')

def pybmf_source_binop_ident(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op(node_value(kids[1])), py_name(node_value(kids[2]))]

def pybmf_emit_bool_and(objects):
    return intern_node(PY_BMF_BOOL_OP, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('and'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_bool_or(objects):
    return intern_node(PY_BMF_BOOL_OP, [pybmf_trivial_string(objects, 'left'), intern_trivial_string('or'), pybmf_trivial_string(objects, 'right')])

def pybmf_emit_subscript_ident_int(objects):
    return intern_node(PY_BMF_SUBSCRIPT, [pybmf_trivial_string(objects, 'object'), pybmf_trivial_int(objects, 'index')])

def pybmf_source_subscript_ident_int(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('['), py_int(int_to_str(node_value(kids[1]))), py_op(']')]

def pybmf_emit_slice_int_int(objects):
    return intern_node(PY_BMF_SLICE, [pybmf_trivial_string(objects, 'object'), pybmf_trivial_int(objects, 'start'), pybmf_trivial_int(objects, 'end')])

def pybmf_emit_tuple2_ident(objects):
    return intern_node(PY_BMF_TUPLE, [pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b')])

def pybmf_emit_set2_int(objects):
    return intern_node(PY_BMF_SET, [pybmf_trivial_int(objects, 'a'), pybmf_trivial_int(objects, 'b')])

def pybmf_emit_lambda1_ident(objects):
    return intern_node(PY_BMF_LAMBDA, [pybmf_trivial_string(objects, 'arg'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_lambda1_ident(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('lambda'), py_name(node_value(kids[0])), py_op(':'), py_name(node_value(kids[1]))]

def pybmf_emit_await(objects):
    return intern_node(PY_BMF_AWAIT, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_await(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('await'), py_name(node_value(kids[0]))]

def pybmf_emit_yield(objects):
    return intern_node(PY_BMF_YIELD, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_yield(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('yield'), py_name(node_value(kids[0]))]

def pybmf_emit_yield_from(objects):
    return intern_node(PY_BMF_YIELD_FROM, [pybmf_trivial_string(objects, 'value')])

def pybmf_emit_break(_objects):
    return intern_node(PY_BMF_BREAK, empty())

def pybmf_emit_continue(_objects):
    return intern_node(PY_BMF_CONTINUE, empty())

def pybmf_emit_global(objects):
    return intern_node(PY_BMF_GLOBAL, [pybmf_trivial_string(objects, 'name')])

def pybmf_emit_nonlocal(objects):
    return intern_node(PY_BMF_NONLOCAL, [pybmf_trivial_string(objects, 'name')])

def pybmf_emit_del(objects):
    return intern_node(PY_BMF_DEL, [pybmf_trivial_string(objects, 'name')])

def pybmf_emit_assert(objects):
    return intern_node(PY_BMF_ASSERT, [pybmf_trivial_string(objects, 'value')])

def pybmf_emit_with_pass(objects):
    return intern_node(PY_BMF_WITH, [pybmf_trivial_string(objects, 'ctx'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_with_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('with'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass')]

def pybmf_emit_with_as_pass(objects):
    return intern_node(PY_BMF_WITH, [pybmf_trivial_string(objects, 'ctx'), pybmf_trivial_string(objects, 'alias'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_with_as_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('with'), py_name(node_value(kids[0])), py_keyword('as'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_try_except_pass(objects):
    return intern_node(PY_BMF_TRY, [intern_trivial_string('except'), pybmf_trivial_string(objects, 'error'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_try_except_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('try'), py_op(':'), py_keyword('pass'), py_keyword('except'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_try_finally_pass(_objects):
    return intern_node(PY_BMF_TRY, [intern_trivial_string('finally'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_try_finally_pass(_object):
    return [py_keyword('try'), py_op(':'), py_keyword('pass'), py_keyword('finally'), py_op(':'), py_keyword('pass')]

def pybmf_emit_try_except_else_finally_pass(objects):
    return intern_node(PY_BMF_TRY, [intern_trivial_string('except-else-finally'), pybmf_trivial_string(objects, 'error'), intern_node(PY_BMF_PASS, empty()), intern_node(PY_BMF_PASS, empty()), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_try_except_else_finally_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('try'), py_op(':'), py_keyword('pass'), py_keyword('except'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass'), py_keyword('else'), py_op(':'), py_keyword('pass'), py_keyword('finally'), py_op(':'), py_keyword('pass')]

def pybmf_emit_async_def(objects):
    return intern_node(PY_BMF_ASYNC_DEF, [pybmf_trivial_string(objects, 'name')])

def pybmf_emit_class_base(objects):
    return intern_node(PY_BMF_CLASS, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'base')])

def pybmf_source_class_base(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('class'), py_name(node_value(kids[0])), py_op('('), py_name(node_value(kids[1])), py_op(')'), py_op(':'), py_keyword('pass')]

def pybmf_emit_decorated_class_base(objects):
    return intern_node(PY_BMF_CLASS, [intern_node(PY_BMF_DECORATOR, [pybmf_trivial_string(objects, 'decorator')]), pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'base')])

def pybmf_source_decorated_class_base(object):
    kids = pybmf_node_kids(object)
    decorator_kids = node_children(kids[0])
    return [py_op('@'), py_name(node_value(decorator_kids[0])), py_keyword('class'), py_name(node_value(kids[1])), py_op('('), py_name(node_value(kids[2])), py_op(')'), py_op(':'), py_keyword('pass')]

def pybmf_emit_decorator(objects):
    return intern_node(PY_BMF_DECORATOR, [pybmf_trivial_string(objects, 'name')])

def pybmf_source_decorator(object):
    kids = pybmf_node_kids(object)
    return [py_op('@'), py_name(node_value(kids[0]))]

def pybmf_emit_decorator_call1(objects):
    return intern_node(PY_BMF_DECORATOR, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'arg')])

def pybmf_source_decorator_call1(object):
    kids = pybmf_node_kids(object)
    return [py_op('@'), py_name(node_value(kids[0])), py_op('('), py_name(node_value(kids[1])), py_op(')')]

def pybmf_emit_decorated_def(objects):
    return intern_node(PY_BMF_DEF, [intern_node(PY_BMF_DECORATOR, [pybmf_trivial_string(objects, 'decorator')]), pybmf_trivial_string(objects, 'name')])

def pybmf_source_decorated_def(object):
    kids = pybmf_node_kids(object)
    decorator_kids = node_children(kids[0])
    return [py_op('@'), py_name(node_value(decorator_kids[0])), py_keyword('def'), py_name(node_value(kids[1])), py_op('('), py_op(')'), py_op(':')]

def pybmf_emit_import_many2(objects):
    return intern_node(PY_BMF_IMPORT_MANY, [pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b')])

def pybmf_source_import_many2(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('import'), py_name(node_value(kids[0])), py_op(','), py_name(node_value(kids[1]))]

def pybmf_emit_import_many3(objects):
    return intern_node(PY_BMF_IMPORT_MANY, [pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b'), pybmf_trivial_string(objects, 'c')])

def pybmf_source_import_many3(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('import'), py_name(node_value(kids[0])), py_op(','), py_name(node_value(kids[1])), py_op(','), py_name(node_value(kids[2]))]

def pybmf_emit_import_alias_many2(objects):
    return intern_node(PY_BMF_IMPORT_MANY, [intern_node(PY_BMF_IMPORT, [pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'alias_a')]), intern_node(PY_BMF_IMPORT, [pybmf_trivial_string(objects, 'b'), pybmf_trivial_string(objects, 'alias_b')])])

def pybmf_source_import_alias_many2(object):
    kids = pybmf_node_kids(object)
    a_kids = node_children(kids[0])
    b_kids = node_children(kids[1])
    return [py_keyword('import'), py_name(node_value(a_kids[0])), py_keyword('as'), py_name(node_value(a_kids[1])), py_op(','), py_name(node_value(b_kids[0])), py_keyword('as'), py_name(node_value(b_kids[1]))]

def pybmf_emit_from_import_many2(objects):
    return intern_node(PY_BMF_FROM_IMPORT, [pybmf_trivial_string(objects, 'module'), pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b')])

def pybmf_source_from_import_many2(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('from'), py_name(node_value(kids[0])), py_keyword('import'), py_name(node_value(kids[1])), py_op(','), py_name(node_value(kids[2]))]

def pybmf_emit_from_import_star(objects):
    return intern_node(PY_BMF_IMPORT_STAR, [pybmf_trivial_string(objects, 'module')])

def pybmf_source_from_import_star(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('from'), py_name(node_value(kids[0])), py_keyword('import'), py_op('*')]

def pybmf_emit_raise_from(objects):
    return intern_node(PY_BMF_RAISE_FROM, [pybmf_trivial_string(objects, 'error'), pybmf_trivial_string(objects, 'cause')])

def pybmf_source_raise_from(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('raise'), py_name(node_value(kids[0])), py_keyword('from'), py_name(node_value(kids[1]))]

def pybmf_emit_if_else_pass(objects):
    return intern_node(PY_BMF_IF_ELSE, [pybmf_trivial_string(objects, 'cond'), intern_node(PY_BMF_PASS, empty()), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_if_else_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('if'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass'), py_keyword('else'), py_op(':'), py_keyword('pass')]

def pybmf_emit_elif_pass(objects):
    return intern_node(PY_BMF_ELIF, [pybmf_trivial_string(objects, 'cond'), pybmf_trivial_string(objects, 'elif_cond'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_elif_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('if'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass'), py_keyword('elif'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_if_elif_else_pass(objects):
    return intern_node(PY_BMF_IF_ELSE, [pybmf_trivial_string(objects, 'cond'), pybmf_trivial_string(objects, 'elif_cond'), intern_node(PY_BMF_PASS, empty()), intern_node(PY_BMF_PASS, empty()), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_if_elif_else_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('if'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass'), py_keyword('elif'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass'), py_keyword('else'), py_op(':'), py_keyword('pass')]

def pybmf_emit_async_for_pass(objects):
    return intern_node(PY_BMF_ASYNC_FOR, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'iter'), intern_node(PY_BMF_PASS, empty())])

def pybmf_emit_async_with_pass(objects):
    return intern_node(PY_BMF_ASYNC_WITH, [pybmf_trivial_string(objects, 'ctx'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_async_with_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('async'), py_keyword('with'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass')]

def pybmf_emit_async_with_as_pass(objects):
    return intern_node(PY_BMF_ASYNC_WITH, [pybmf_trivial_string(objects, 'ctx'), pybmf_trivial_string(objects, 'alias'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_async_with_as_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('async'), py_keyword('with'), py_name(node_value(kids[0])), py_keyword('as'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_except_as_pass(objects):
    return intern_node(PY_BMF_EXCEPT_AS, [pybmf_trivial_string(objects, 'error'), pybmf_trivial_string(objects, 'alias'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_except_as_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('except'), py_name(node_value(kids[0])), py_keyword('as'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_match_header(objects):
    return intern_node(PY_BMF_MATCH, [pybmf_trivial_string(objects, 'subject')])

def pybmf_source_match_header(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('match'), py_name(node_value(kids[0])), py_op(':')]

def pybmf_emit_case_pass(objects):
    return intern_node(PY_BMF_CASE, [pybmf_trivial_string(objects, 'pattern'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_case_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('case'), py_name(node_value(kids[0])), py_op(':'), py_keyword('pass')]

def pybmf_emit_case_guard_pass(objects):
    return intern_node(PY_BMF_CASE, [pybmf_trivial_string(objects, 'pattern'), pybmf_trivial_string(objects, 'guard'), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_case_guard_pass(object):
    kids = pybmf_node_kids(object)
    return [py_keyword('case'), py_name(node_value(kids[0])), py_keyword('if'), py_name(node_value(kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_match_as(objects):
    return intern_node(PY_BMF_MATCH_AS, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'alias')])

def pybmf_source_match_as(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_keyword('as'), py_name(node_value(kids[1]))]

def pybmf_emit_list_comp(objects):
    return intern_node(PY_BMF_COMP, [intern_trivial_string('list'), pybmf_trivial_string(objects, 'expr'), pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'iter')])

def pybmf_source_list_comp(object):
    kids = pybmf_node_kids(object)
    return [py_op('['), py_name(node_value(kids[1])), py_keyword('for'), py_name(node_value(kids[2])), py_keyword('in'), py_name(node_value(kids[3])), py_op(']')]

def pybmf_emit_dict_comp(objects):
    return intern_node(PY_BMF_COMP, [intern_trivial_string('dict'), pybmf_trivial_string(objects, 'key'), pybmf_trivial_string(objects, 'value'), pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'iter')])

def pybmf_source_dict_comp(object):
    kids = pybmf_node_kids(object)
    return [py_op('{'), py_name(node_value(kids[1])), py_op(':'), py_name(node_value(kids[2])), py_keyword('for'), py_name(node_value(kids[3])), py_keyword('in'), py_name(node_value(kids[4])), py_op('}')]

def pybmf_emit_gen_exp(objects):
    return intern_node(PY_BMF_GENEXP, [pybmf_trivial_string(objects, 'expr'), pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'iter')])

def pybmf_emit_set_comp(objects):
    return intern_node(PY_BMF_SETCOMP, [pybmf_trivial_string(objects, 'expr'), pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'iter')])

def pybmf_source_set_comp(object):
    kids = pybmf_node_kids(object)
    return [py_op('{'), py_name(node_value(kids[0])), py_keyword('for'), py_name(node_value(kids[1])), py_keyword('in'), py_name(node_value(kids[2])), py_op('}')]

def pybmf_emit_kwarg(objects):
    return intern_node(PY_BMF_KWARG, [pybmf_trivial_string(objects, 'key'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_kwarg(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('='), py_name(node_value(kids[1]))]

def pybmf_emit_star_arg(objects):
    return intern_node(PY_BMF_STARARG, [intern_trivial_string('*'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_star_arg(object):
    kids = pybmf_node_kids(object)
    return [py_op(node_value(kids[0])), py_name(node_value(kids[1]))]

def pybmf_emit_star_star_arg(objects):
    return intern_node(PY_BMF_STARARG, [intern_trivial_string('**'), pybmf_trivial_string(objects, 'value')])

def pybmf_emit_call_kwarg1(objects):
    return intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'callee'), intern_node(PY_BMF_KWARG, [pybmf_trivial_string(objects, 'key'), pybmf_trivial_string(objects, 'value')])])

def pybmf_source_call_kwarg1(object):
    kids = pybmf_node_kids(object)
    kw_kids = node_children(kids[1])
    return [py_name(node_value(kids[0])), py_op('('), py_name(node_value(kw_kids[0])), py_op('='), py_name(node_value(kw_kids[1])), py_op(')')]

def pybmf_emit_call_star1(objects):
    return intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'callee'), intern_node(PY_BMF_STARARG, [intern_trivial_string('*'), pybmf_trivial_string(objects, 'value')])])

def pybmf_source_call_star1(object):
    kids = pybmf_node_kids(object)
    star_kids = node_children(kids[1])
    return [py_name(node_value(kids[0])), py_op('('), py_op(node_value(star_kids[0])), py_name(node_value(star_kids[1])), py_op(')')]

def pybmf_emit_call_star_star1(objects):
    return intern_node(PY_BMF_CALL, [pybmf_trivial_string(objects, 'callee'), intern_node(PY_BMF_STARARG, [intern_trivial_string('**'), pybmf_trivial_string(objects, 'value')])])

def pybmf_emit_default_param_int(objects):
    return intern_node(PY_BMF_DEFAULT, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_int(objects, 'value')])

def pybmf_source_default_param_int(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('='), py_int(int_to_str(node_value(kids[1])))]

def pybmf_emit_default_param_string(objects):
    return intern_node(PY_BMF_DEFAULT, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_default_param_string(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op('='), py_string(node_value(kids[1]))]

def pybmf_emit_typed_param(objects):
    return intern_node(PY_BMF_TYPED_PARAM, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'type')])

def pybmf_source_typed_param(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op(':'), py_name(node_value(kids[1]))]

def pybmf_emit_typed_default_param_int(objects):
    return intern_node(PY_BMF_DEFAULT, [intern_node(PY_BMF_TYPED_PARAM, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'type')]), pybmf_trivial_int(objects, 'value')])

def pybmf_source_typed_default_param_int(object):
    kids = pybmf_node_kids(object)
    typed_kids = node_children(kids[0])
    return [py_name(node_value(typed_kids[0])), py_op(':'), py_name(node_value(typed_kids[1])), py_op('='), py_int(int_to_str(node_value(kids[1])))]

def pybmf_emit_typed_default_param_string(objects):
    return intern_node(PY_BMF_DEFAULT, [intern_node(PY_BMF_TYPED_PARAM, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'type')]), pybmf_trivial_string(objects, 'value')])

def pybmf_source_typed_default_param_string(object):
    kids = pybmf_node_kids(object)
    typed_kids = node_children(kids[0])
    return [py_name(node_value(typed_kids[0])), py_op(':'), py_name(node_value(typed_kids[1])), py_op('='), py_string(node_value(kids[1]))]

def pybmf_emit_def1_typed_default_int(objects):
    return intern_node(PY_BMF_DEF, [pybmf_trivial_string(objects, 'name'), intern_node(PY_BMF_DEFAULT, [intern_node(PY_BMF_TYPED_PARAM, [pybmf_trivial_string(objects, 'arg'), pybmf_trivial_string(objects, 'type')]), pybmf_trivial_int(objects, 'value')])])

def pybmf_source_def1_typed_default_int(object):
    kids = pybmf_node_kids(object)
    default_kids = node_children(kids[1])
    typed_kids = node_children(default_kids[0])
    return [py_keyword('def'), py_name(node_value(kids[0])), py_op('('), py_name(node_value(typed_kids[0])), py_op(':'), py_name(node_value(typed_kids[1])), py_op('='), py_int(int_to_str(node_value(default_kids[1]))), py_op(')'), py_op(':')]

def pybmf_emit_def_return_annotation(objects):
    return intern_node(PY_BMF_RET_ANN, [pybmf_trivial_string(objects, 'name'), pybmf_trivial_string(objects, 'type')])

def pybmf_emit_walrus_ident(objects):
    return intern_node(PY_BMF_WALRUS, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_walrus_ident(object):
    kids = pybmf_node_kids(object)
    return [py_name(node_value(kids[0])), py_op(':='), py_name(node_value(kids[1]))]

def pybmf_emit_if_walrus_pass(objects):
    return intern_node(PY_BMF_IF, [intern_node(PY_BMF_WALRUS, [pybmf_trivial_string(objects, 'target'), pybmf_trivial_string(objects, 'value')]), intern_node(PY_BMF_PASS, empty())])

def pybmf_source_if_walrus_pass(object):
    kids = pybmf_node_kids(object)
    walrus_kids = node_children(kids[0])
    return [py_keyword('if'), py_name(node_value(walrus_kids[0])), py_op(':='), py_name(node_value(walrus_kids[1])), py_op(':'), py_keyword('pass')]

def pybmf_emit_float(objects):
    return intern_node(PY_BMF_FLOAT, [pybmf_trivial_string(objects, 'value')])

def pybmf_emit_bytes(objects):
    return intern_node(PY_BMF_BYTES, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_bytes(object):
    kids = pybmf_node_kids(object)
    return [py_bytes(node_value(kids[0]))]

def pybmf_emit_ellipsis(_objects):
    return intern_node(PY_BMF_ELLIPSIS, empty())

def pybmf_source_ellipsis(_object):
    return [py_op('...')]

def pybmf_emit_fstring(objects):
    return intern_node(PY_BMF_FSTRING, [pybmf_trivial_string(objects, 'value')])

def pybmf_source_fstring(object):
    kids = pybmf_node_kids(object)
    return [py_fstring(node_value(kids[0]))]

def pybmf_emit_fstring_format(objects):
    return intern_node(PY_BMF_FSTRING, [pybmf_trivial_string(objects, 'prefix'), pybmf_trivial_string(objects, 'value')])

def pybmf_source_fstring_format(object):
    kids = pybmf_node_kids(object)
    return [py_fstring(node_value(kids[0])), py_op('{'), py_name(node_value(kids[1])), py_op('}')]

def pybmf_emit_ifexp(objects):
    return intern_node(PY_BMF_IFEXP, [pybmf_trivial_string(objects, 'body'), pybmf_trivial_string(objects, 'test'), pybmf_trivial_string(objects, 'orelse')])

def pybmf_emit_attr_assign_int(objects):
    return intern_node(PY_BMF_ATTR_ASSIGN, [pybmf_trivial_string(objects, 'object'), pybmf_trivial_string(objects, 'field'), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_subscript_assign_int(objects):
    return intern_node(PY_BMF_SUB_ASSIGN, [pybmf_trivial_string(objects, 'object'), pybmf_trivial_int(objects, 'index'), pybmf_trivial_int(objects, 'value')])

def pybmf_emit_unpack2_ident(objects):
    return intern_node(PY_BMF_UNPACK, [pybmf_trivial_string(objects, 'a'), pybmf_trivial_string(objects, 'b'), pybmf_trivial_string(objects, 'value')])

def python_bmf_rule_name(r):
    return r[0]

def python_bmf_find_rule(rule_name, rules):
    if is_nil(rules):
        return empty()
    else:
        if str_eq(python_bmf_rule_name(rules[0]), rule_name):
            return rules[0]
        else:
            return python_bmf_find_rule(rule_name, rules[1:])

def apply_python_bmf_rule(rule_name, object_stream):
    rule = python_bmf_find_rule(rule_name, python_bmf_rules)
    return apply_object_rule(rule, object_stream)

PY_BMF_IMPORT = make_nodeid(1, 2, 99, 501)
PY_BMF_FROM_IMPORT = make_nodeid(1, 2, 99, 502)
PY_BMF_DEF = make_nodeid(1, 2, 99, 503)
PY_BMF_CLASS = make_nodeid(1, 2, 99, 504)
PY_BMF_ASSIGN = make_nodeid(1, 2, 99, 505)
PY_BMF_RETURN = make_nodeid(1, 2, 99, 506)
PY_BMF_RAISE = make_nodeid(1, 2, 99, 507)
PY_BMF_PASS = make_nodeid(1, 2, 99, 508)
PY_BMF_IF = make_nodeid(1, 2, 99, 509)
PY_BMF_WHILE = make_nodeid(1, 2, 99, 510)
PY_BMF_FOR = make_nodeid(1, 2, 99, 511)
PY_BMF_CALL = make_nodeid(1, 2, 99, 512)
PY_BMF_INT = make_nodeid(1, 2, 99, 513)
PY_BMF_STRING = make_nodeid(1, 2, 99, 514)
PY_BMF_IDENT = make_nodeid(1, 2, 99, 515)
PY_BMF_ATTR = make_nodeid(1, 2, 99, 516)
PY_BMF_METHOD_CALL = make_nodeid(1, 2, 99, 517)
PY_BMF_LIST = make_nodeid(1, 2, 99, 518)
PY_BMF_DICT = make_nodeid(1, 2, 99, 519)
PY_BMF_ANNOTATED = make_nodeid(1, 2, 99, 520)
PY_BMF_AUG_ASSIGN = make_nodeid(1, 2, 99, 521)
PY_BMF_BINOP = make_nodeid(1, 2, 99, 522)
PY_BMF_MODULE = make_nodeid(1, 2, 99, 523)
PY_BMF_BOOL = make_nodeid(1, 2, 99, 524)
PY_BMF_NONE = make_nodeid(1, 2, 99, 525)
PY_BMF_UNARY = make_nodeid(1, 2, 99, 526)
PY_BMF_COMPARE = make_nodeid(1, 2, 99, 527)
PY_BMF_BOOL_OP = make_nodeid(1, 2, 99, 528)
PY_BMF_SUBSCRIPT = make_nodeid(1, 2, 99, 529)
PY_BMF_SLICE = make_nodeid(1, 2, 99, 530)
PY_BMF_TUPLE = make_nodeid(1, 2, 99, 531)
PY_BMF_SET = make_nodeid(1, 2, 99, 532)
PY_BMF_LAMBDA = make_nodeid(1, 2, 99, 533)
PY_BMF_AWAIT = make_nodeid(1, 2, 99, 534)
PY_BMF_YIELD = make_nodeid(1, 2, 99, 535)
PY_BMF_BREAK = make_nodeid(1, 2, 99, 536)
PY_BMF_CONTINUE = make_nodeid(1, 2, 99, 537)
PY_BMF_GLOBAL = make_nodeid(1, 2, 99, 538)
PY_BMF_NONLOCAL = make_nodeid(1, 2, 99, 539)
PY_BMF_DEL = make_nodeid(1, 2, 99, 540)
PY_BMF_ASSERT = make_nodeid(1, 2, 99, 541)
PY_BMF_WITH = make_nodeid(1, 2, 99, 542)
PY_BMF_TRY = make_nodeid(1, 2, 99, 543)
PY_BMF_ASYNC_DEF = make_nodeid(1, 2, 99, 544)
PY_BMF_DECORATOR = make_nodeid(1, 2, 99, 545)
PY_BMF_ASYNC_FOR = make_nodeid(1, 2, 99, 546)
PY_BMF_ASYNC_WITH = make_nodeid(1, 2, 99, 547)
PY_BMF_IF_ELSE = make_nodeid(1, 2, 99, 548)
PY_BMF_ELIF = make_nodeid(1, 2, 99, 549)
PY_BMF_RAISE_FROM = make_nodeid(1, 2, 99, 550)
PY_BMF_IMPORT_STAR = make_nodeid(1, 2, 99, 551)
PY_BMF_IMPORT_MANY = make_nodeid(1, 2, 99, 552)
PY_BMF_EXCEPT_AS = make_nodeid(1, 2, 99, 553)
PY_BMF_MATCH = make_nodeid(1, 2, 99, 554)
PY_BMF_CASE = make_nodeid(1, 2, 99, 555)
PY_BMF_COMP = make_nodeid(1, 2, 99, 556)
PY_BMF_GENEXP = make_nodeid(1, 2, 99, 557)
PY_BMF_KWARG = make_nodeid(1, 2, 99, 558)
PY_BMF_STARARG = make_nodeid(1, 2, 99, 559)
PY_BMF_DEFAULT = make_nodeid(1, 2, 99, 560)
PY_BMF_TYPED_PARAM = make_nodeid(1, 2, 99, 561)
PY_BMF_RET_ANN = make_nodeid(1, 2, 99, 562)
PY_BMF_WALRUS = make_nodeid(1, 2, 99, 563)
PY_BMF_FLOAT = make_nodeid(1, 2, 99, 564)
PY_BMF_BYTES = make_nodeid(1, 2, 99, 565)
PY_BMF_ELLIPSIS = make_nodeid(1, 2, 99, 566)
PY_BMF_ATTR_ASSIGN = make_nodeid(1, 2, 99, 567)
PY_BMF_SUB_ASSIGN = make_nodeid(1, 2, 99, 568)
PY_BMF_UNPACK = make_nodeid(1, 2, 99, 569)
PY_BMF_FSTRING = make_nodeid(1, 2, 99, 570)
PY_BMF_IFEXP = make_nodeid(1, 2, 99, 571)
PY_BMF_SETCOMP = make_nodeid(1, 2, 99, 572)
PY_BMF_YIELD_FROM = make_nodeid(1, 2, 99, 573)
PY_BMF_MATCH_AS = make_nodeid(1, 2, 99, 574)
python_source_keywords = ['import', 'from', 'as', 'def', 'return', 'class', 'pass', 'if', 'else', 'elif', 'while', 'for', 'in', 'with', 'async', 'await', 'try', 'except', 'finally', 'raise', 'True', 'False', 'None', 'not', 'and', 'or', 'yield', 'global', 'nonlocal', 'del', 'assert', 'match', 'case', 'lambda', 'is', 'type']
python_source_ops = ['**=', '//=', '>>=', '<<=', ':=', '==', '!=', '<=', '>=', '->', '@=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '**', '//', '<<', '>>', '...', '(', ')', '[', ']', '{', '}', ',', ':', '.', ';', '@', '=', '+', '-', '*', '/', '%', '&', '|', '^', '~', '<', '>', '!']
python_bmf_native_section = [bmf_native('pybmf-emit-import', pybmf_emit_import, PY_BMF_IMPORT), bmf_native('pybmf-emit-from-import', pybmf_emit_from_import, PY_BMF_FROM_IMPORT), bmf_native('pybmf-emit-def', pybmf_emit_def, PY_BMF_DEF), bmf_native('pybmf-emit-class', pybmf_emit_class, PY_BMF_CLASS), bmf_native('pybmf-emit-assign-ident', pybmf_emit_assign_ident, PY_BMF_ASSIGN), bmf_native('pybmf-emit-return-ident', pybmf_emit_return_ident, PY_BMF_RETURN), bmf_native('pybmf-emit-raise', pybmf_emit_raise, PY_BMF_RAISE), bmf_native('pybmf-emit-if', pybmf_emit_if, PY_BMF_IF), bmf_native('pybmf-emit-for', pybmf_emit_for, PY_BMF_FOR), bmf_native('pybmf-emit-call0', pybmf_emit_call0, PY_BMF_CALL), bmf_native('pybmf-emit-binop-sub', pybmf_emit_binop_sub, PY_BMF_BINOP), bmf_native('pybmf-emit-compare-eq', pybmf_emit_compare_eq, PY_BMF_COMPARE), bmf_native('pybmf-emit-await', pybmf_emit_await, PY_BMF_AWAIT), bmf_native('pybmf-emit-yield-from', pybmf_emit_yield_from, PY_BMF_YIELD_FROM), bmf_native('pybmf-emit-fstring', pybmf_emit_fstring, PY_BMF_FSTRING), bmf_native('pybmf-emit-ifexp', pybmf_emit_ifexp, PY_BMF_IFEXP), bmf_native('pybmf-emit-set-comp', pybmf_emit_set_comp, PY_BMF_SETCOMP), bmf_native('pybmf-emit-match-as', pybmf_emit_match_as, PY_BMF_MATCH_AS)]
python_bmf_section = python_bmf_second
python_recipe_section = form_rule_recipe_section('python', [compiler_rule('python', 'import', 'Python import source objects', pybmf_emit_import), compiler_rule('python', 'def', 'Python function source objects', pybmf_emit_def), compiler_rule('python', 'class', 'Python class source objects', pybmf_emit_class), compiler_rule('python', 'assign', 'Python assignment source objects', pybmf_emit_assign_ident), compiler_rule('python', 'return', 'Python return source objects', pybmf_emit_return_ident), compiler_rule('python', 'match', 'Python match source objects', pybmf_emit_match_header), compiler_rule('python', 'fstring', 'Python f-string source objects', pybmf_emit_fstring)])
python_form_source = form_source('python', [python_bmf_section, python_recipe_section])
python_bmf_dialect = bmf_dialect('python', form_section_object(python_bmf_section), python_bmf_native_section, python_bmf_rules)

if __name__ == '__main__':
    section
    _python_bmf_
    _
    import_as
    ___
    'import'
    _module_name
    'as'
    _alias_name
    __
    pybmf_emit_import
    __
    pybmf_source_import_as_
    import_
    ___
    'import'
    _module_name
    __
    pybmf_emit_import_bare_
    import_many2
    ___
    'import'
    _a_name
    ','
    _b_name
    __
    pybmf_emit_import_many2
    __
    pybmf_source_import_many2_
    import_many3
    ___
    'import'
    _a_name
    ','
    _b_name
    ','
    _c_name
    __
    pybmf_emit_import_many3
    __
    pybmf_source_import_many3_
    import_alias_many2
    ___
    'import'
    _a_name
    'as'
    _alias_a_name
    ','
    _b_name
    'as'
    _alias_b_name
    __
    pybmf_emit_import_alias_many2
    __
    pybmf_source_import_alias_many2_
    from_import
    ___
    'from'
    _module_name
    'import'
    _name_name
    __
    pybmf_emit_from_import
    __
    pybmf_source_from_import_
    from_import_many2
    ___
    'from'
    _module_name
    'import'
    _a_name
    ','
    _b_name
    __
    pybmf_emit_from_import_many2
    __
    pybmf_source_from_import_many2_
    from_import_star
    ___
    'from'
    _module_name
    'import'
    '*'
    __
    pybmf_emit_from_import_star
    __
    pybmf_source_from_import_star_
    decorator
    ___
    '@'
    _name_name
    __
    pybmf_emit_decorator
    __
    pybmf_source_decorator_
    decorator_call1
    ___
    '@'
    _name_name
    '('
    _arg_name
    ')'
    __
    pybmf_emit_decorator_call1
    __
    pybmf_source_decorator_call1_
    decorated_def
    ___
    '@'
    _decorator_name
    'def'
    _name_name
    '('
    ')'
    ':'
    __
    pybmf_emit_decorated_def
    __
    pybmf_source_decorated_def_
    def_
    ___
    'def'
    _name_name
    '('
    ')'
    ':'
    __
    pybmf_emit_def
    __
    pybmf_source_def_
    def2
    ___
    'def'
    _name_name
    '('
    _a_name
    ','
    _b_name
    ')'
    ':'
    __
    pybmf_emit_def2
    __
    pybmf_source_def2_
    class_
    ___
    'class'
    _name_name
    ':'
    'pass'
    __
    pybmf_emit_class
    __
    pybmf_source_class_
    assign_int
    ___
    _target_name
    '='
    _value_int
    __
    pybmf_emit_assign_int
    __
    pybmf_source_assign_int_
    assign_ident
    ___
    _target_name
    '='
    _value_name
    __
    pybmf_emit_assign_ident
    __
    pybmf_source_assign_ident_
    assign_string
    ___
    _target_name
    '='
    _value_string
    __
    pybmf_emit_assign_string
    __
    pybmf_source_assign_string_
    return_int
    ___
    'return'
    _value_int
    __
    pybmf_emit_return_int
    __
    pybmf_source_return_int_
    return_ident
    ___
    'return'
    _value_name
    __
    pybmf_emit_return_ident
    __
    pybmf_source_return_ident_
    return_string
    ___
    'return'
    _value_string
    __
    pybmf_emit_return_string
    __
    pybmf_source_return_string_
    return_plus_ident
    ___
    'return'
    _left_name
    '+'
    _right_name
    __
    pybmf_emit_return_plus_ident
    __
    pybmf_source_return_plus_ident_
    raise_
    ___
    'raise'
    _value_name
    __
    pybmf_emit_raise
    __
    pybmf_source_raise_
    raise_from
    ___
    'raise'
    _error_name
    'from'
    _cause_name
    __
    pybmf_emit_raise_from
    __
    pybmf_source_raise_from_
    pass_
    ___
    'pass'
    __
    pybmf_emit_pass_
    break_
    ___
    'break'
    __
    pybmf_emit_break_
    continue_
    ___
    'continue'
    __
    pybmf_emit_continue_
    global_
    ___
    'global'
    _name_name
    __
    pybmf_emit_global_
    nonlocal_
    ___
    'nonlocal'
    _name_name
    __
    pybmf_emit_nonlocal_
    del_
    ___
    'del'
    _name_name
    __
    pybmf_emit_del_
    assert_ident
    ___
    'assert'
    _value_name
    __
    pybmf_emit_assert_
    if_header
    ___
    'if'
    _cond_name
    ':'
    'pass'
    __
    pybmf_emit_if
    __
    pybmf_source_if_pass_
    ifexp_ident
    ___
    _body_name
    'if'
    _test_name
    'else'
    _orelse_name
    __
    pybmf_emit_ifexp_
    if_else_pass
    ___
    'if'
    _cond_name
    ':'
    'pass'
    'else'
    ':'
    'pass'
    __
    pybmf_emit_if_else_pass
    __
    pybmf_source_if_else_pass_
    elif_pass
    ___
    'if'
    _cond_name
    ':'
    'pass'
    'elif'
    _elif_cond_name
    ':'
    'pass'
    __
    pybmf_emit_elif_pass
    __
    pybmf_source_elif_pass_
    if_elif_else_pass
    ___
    'if'
    _cond_name
    ':'
    'pass'
    'elif'
    _elif_cond_name
    ':'
    'pass'
    'else'
    ':'
    'pass'
    __
    pybmf_emit_if_elif_else_pass
    __
    pybmf_source_if_elif_else_pass_
    while_header
    ___
    'while'
    _cond_name
    ':'
    'pass'
    __
    pybmf_emit_while
    __
    pybmf_source_while_pass_
    for_header
    ___
    'for'
    _target_name
    'in'
    _iter_name
    ':'
    'pass'
    __
    pybmf_emit_for
    __
    pybmf_source_for_pass_
    with_pass
    ___
    'with'
    _ctx_name
    ':'
    'pass'
    __
    pybmf_emit_with_pass
    __
    pybmf_source_with_pass_
    with_as_pass
    ___
    'with'
    _ctx_name
    'as'
    _alias_name
    ':'
    'pass'
    __
    pybmf_emit_with_as_pass
    __
    pybmf_source_with_as_pass_
    async_for_pass
    ___
    'async'
    'for'
    _target_name
    'in'
    _iter_name
    ':'
    'pass'
    __
    pybmf_emit_async_for_pass_
    async_with_pass
    ___
    'async'
    'with'
    _ctx_name
    ':'
    'pass'
    __
    pybmf_emit_async_with_pass
    __
    pybmf_source_async_with_pass_
    async_with_as_pass
    ___
    'async'
    'with'
    _ctx_name
    'as'
    _alias_name
    ':'
    'pass'
    __
    pybmf_emit_async_with_as_pass
    __
    pybmf_source_async_with_as_pass_
    try_except_pass
    ___
    'try'
    ':'
    'pass'
    'except'
    _error_name
    ':'
    'pass'
    __
    pybmf_emit_try_except_pass
    __
    pybmf_source_try_except_pass_
    except_as_pass
    ___
    'except'
    _error_name
    'as'
    _alias_name
    ':'
    'pass'
    __
    pybmf_emit_except_as_pass
    __
    pybmf_source_except_as_pass_
    try_finally_pass
    ___
    'try'
    ':'
    'pass'
    'finally'
    ':'
    'pass'
    __
    pybmf_emit_try_finally_pass
    __
    pybmf_source_try_finally_pass_
    try_except_else_finally_pass
    ___
    'try'
    ':'
    'pass'
    'except'
    _error_name
    ':'
    'pass'
    'else'
    ':'
    'pass'
    'finally'
    ':'
    'pass'
    __
    pybmf_emit_try_except_else_finally_pass
    __
    pybmf_source_try_except_else_finally_pass_
    async_def
    ___
    'async'
    'def'
    _name_name
    '('
    ')'
    ':'
    __
    pybmf_emit_async_def_
    call0
    ___
    _callee_name
    '('
    ')'
    __
    pybmf_emit_call0
    __
    pybmf_source_call0_
    call1_ident
    ___
    _callee_name
    '('
    _arg_name
    ')'
    __
    pybmf_emit_call1_ident
    __
    pybmf_source_call1_ident_
    kwarg
    ___
    _key_name
    '='
    _value_name
    __
    pybmf_emit_kwarg
    __
    pybmf_source_kwarg_
    star_arg
    ___
    '*'
    _value_name
    __
    pybmf_emit_star_arg
    __
    pybmf_source_star_arg_
    star_star_arg
    ___
    '**'
    _value_name
    __
    pybmf_emit_star_star_arg
    __
    pybmf_source_star_arg_
    call_kwarg1
    ___
    _callee_name
    '('
    _key_name
    '='
    _value_name
    ')'
    __
    pybmf_emit_call_kwarg1
    __
    pybmf_source_call_kwarg1_
    call_star1
    ___
    _callee_name
    '('
    '*'
    _value_name
    ')'
    __
    pybmf_emit_call_star1
    __
    pybmf_source_call_star1_
    call_star_star1
    ___
    _callee_name
    '('
    '**'
    _value_name
    ')'
    __
    pybmf_emit_call_star_star1
    __
    pybmf_source_call_star1_
    assign_call2_ident
    ___
    _target_name
    '='
    _callee_name
    '('
    _a_name
    ','
    _b_name
    ')'
    __
    pybmf_emit_assign_call2_ident_
    attr
    ___
    _object_name
    '.'
    _field_name
    __
    pybmf_emit_attr
    __
    pybmf_source_attr_
    method_call0
    ___
    _object_name
    '.'
    _method_name
    '('
    ')'
    __
    pybmf_emit_method_call0
    __
    pybmf_source_method_call0_
    subscript_ident_int
    ___
    _object_name
    '['
    _index_int
    ']'
    __
    pybmf_emit_subscript_ident_int
    __
    pybmf_source_subscript_ident_int_
    slice_int_int
    ___
    _object_name
    '['
    _start_int
    ':'
    _end_int
    ']'
    __
    pybmf_emit_slice_int_int_
    list3_int
    ___
    '['
    _a_int
    ','
    _b_int
    ','
    _c_int
    ']'
    __
    pybmf_emit_list3_int_
    tuple2_ident
    ___
    '('
    _a_name
    ','
    _b_name
    ')'
    __
    pybmf_emit_tuple2_ident_
    set2_int
    ___
    '{'
    _a_int
    ','
    _b_int
    '}'
    __
    pybmf_emit_set2_int_
    dict1_ident_int
    ___
    '{'
    _key_name
    ':'
    _value_int
    '}'
    __
    pybmf_emit_dict1_ident_int_
    list_comp
    ___
    '['
    _expr_name
    'for'
    _target_name
    'in'
    _iter_name
    ']'
    __
    pybmf_emit_list_comp
    __
    pybmf_source_list_comp_
    dict_comp
    ___
    '{'
    _key_name
    ':'
    _value_name
    'for'
    _target_name
    'in'
    _iter_name
    '}'
    __
    pybmf_emit_dict_comp
    __
    pybmf_source_dict_comp_
    gen_exp
    ___
    '('
    _expr_name
    'for'
    _target_name
    'in'
    _iter_name
    ')'
    __
    pybmf_emit_gen_exp_
    set_comp
    ___
    '{'
    _expr_name
    'for'
    _target_name
    'in'
    _iter_name
    '}'
    __
    pybmf_emit_set_comp
    __
    pybmf_source_set_comp_
    annotated_assign_int
    ___
    _target_name
    ':'
    _type_name
    '='
    _value_int
    __
    pybmf_emit_annotated_assign_int_
    typed_param
    ___
    _name_name
    ':'
    _type_name
    __
    pybmf_emit_typed_param
    __
    pybmf_source_typed_param_
    default_param_int
    ___
    _name_name
    '='
    _value_int
    __
    pybmf_emit_default_param_int
    __
    pybmf_source_default_param_int_
    default_param_string
    ___
    _name_name
    '='
    _value_string
    __
    pybmf_emit_default_param_string
    __
    pybmf_source_default_param_string_
    typed_default_param_int
    ___
    _name_name
    ':'
    _type_name
    '='
    _value_int
    __
    pybmf_emit_typed_default_param_int
    __
    pybmf_source_typed_default_param_int_
    typed_default_param_string
    ___
    _name_name
    ':'
    _type_name
    '='
    _value_string
    __
    pybmf_emit_typed_default_param_string
    __
    pybmf_source_typed_default_param_string_
    def1_typed_default_int
    ___
    'def'
    _name_name
    '('
    _arg_name
    ':'
    _type_name
    '='
    _value_int
    ')'
    ':'
    __
    pybmf_emit_def1_typed_default_int
    __
    pybmf_source_def1_typed_default_int_
    def_return_annotation
    ___
    'def'
    _name_name
    '('
    ')'
    '->'
    _type_name
    ':'
    __
    pybmf_emit_def_return_annotation_
    plus_assign_int
    ___
    _target_name
    '+='
    _value_int
    __
    pybmf_emit_aug_assign_int_
    attr_assign_int
    ___
    _object_name
    '.'
    _field_name
    '='
    _value_int
    __
    pybmf_emit_attr_assign_int_
    subscript_assign_int
    ___
    _object_name
    '['
    _index_int
    ']'
    '='
    _value_int
    __
    pybmf_emit_subscript_assign_int_
    unpack2_ident
    ___
    _a_name
    ','
    _b_name
    '='
    _value_name
    __
    pybmf_emit_unpack2_ident_
    walrus_ident
    ___
    _target_name
    ':='
    _value_name
    __
    pybmf_emit_walrus_ident
    __
    pybmf_source_walrus_ident_
    if_walrus_pass
    ___
    'if'
    _target_name
    ':='
    _value_name
    ':'
    'pass'
    __
    pybmf_emit_if_walrus_pass
    __
    pybmf_source_if_walrus_pass_
    class_base
    ___
    'class'
    _name_name
    '('
    _base_name
    ')'
    ':'
    'pass'
    __
    pybmf_emit_class_base
    __
    pybmf_source_class_base_
    decorated_class_base
    ___
    '@'
    _decorator_name
    'class'
    _name_name
    '('
    _base_name
    ')'
    ':'
    'pass'
    __
    pybmf_emit_decorated_class_base
    __
    pybmf_source_decorated_class_base_
    bool_true
    ___
    'True'
    __
    pybmf_emit_bool_true_
    bool_false
    ___
    'False'
    __
    pybmf_emit_bool_false_
    none
    ___
    'None'
    __
    pybmf_emit_none_
    not_ident
    ___
    'not'
    _value_name
    __
    pybmf_emit_unary_not
    __
    pybmf_source_unary_not_
    neg_int
    ___
    '-'
    _value_int
    __
    pybmf_emit_unary_neg_int_
    pos_int
    ___
    '+'
    _value_int
    __
    pybmf_emit_unary_plus_int_
    invert_ident
    ___
    '~'
    _value_name
    __
    pybmf_emit_unary_invert_
    compare_eq_ident
    ___
    _left_name
    '=='
    _right_name
    __
    pybmf_emit_compare_eq
    __
    pybmf_source_compare_op_
    compare_lt_ident
    ___
    _left_name
    '<'
    _right_name
    __
    pybmf_emit_compare_lt
    __
    pybmf_source_compare_op_
    compare_ne_ident
    ___
    _left_name
    '!='
    _right_name
    __
    pybmf_emit_compare_ne
    __
    pybmf_source_compare_op_
    compare_gt_ident
    ___
    _left_name
    '>'
    _right_name
    __
    pybmf_emit_compare_gt
    __
    pybmf_source_compare_op_
    compare_gte_ident
    ___
    _left_name
    '>='
    _right_name
    __
    pybmf_emit_compare_gte
    __
    pybmf_source_compare_op_
    compare_lte_ident
    ___
    _left_name
    '<='
    _right_name
    __
    pybmf_emit_compare_lte
    __
    pybmf_source_compare_op_
    compare_in_ident
    ___
    _left_name
    'in'
    _right_name
    __
    pybmf_emit_compare_in
    __
    pybmf_source_compare_word_
    compare_not_in_ident
    ___
    _left_name
    'not'
    'in'
    _right_name
    __
    pybmf_emit_compare_not_in
    __
    pybmf_source_compare_not_in_
    compare_is_ident
    ___
    _left_name
    'is'
    _right_name
    __
    pybmf_emit_compare_is
    __
    pybmf_source_compare_word_
    compare_is_not_ident
    ___
    _left_name
    'is'
    'not'
    _right_name
    __
    pybmf_emit_compare_is_not
    __
    pybmf_source_compare_is_not_
    compare_chain_lt_lte
    ___
    _left_name
    '<'
    _middle_name
    '<='
    _right_name
    __
    pybmf_emit_compare_chain_lt_lte
    __
    pybmf_source_compare_chain_
    binop_sub_ident
    ___
    _left_name
    '-'
    _right_name
    __
    pybmf_emit_binop_sub
    __
    pybmf_source_binop_ident_
    binop_mul_ident
    ___
    _left_name
    '*'
    _right_name
    __
    pybmf_emit_binop_mul
    __
    pybmf_source_binop_ident_
    binop_div_ident
    ___
    _left_name
    '/'
    _right_name
    __
    pybmf_emit_binop_div
    __
    pybmf_source_binop_ident_
    binop_mod_ident
    ___
    _left_name
    '%'
    _right_name
    __
    pybmf_emit_binop_mod
    __
    pybmf_source_binop_ident_
    binop_pow_ident
    ___
    _left_name
    '**'
    _right_name
    __
    pybmf_emit_binop_pow
    __
    pybmf_source_binop_ident_
    binop_floor_div_ident
    ___
    _left_name
    '//'
    _right_name
    __
    pybmf_emit_binop_floor_div
    __
    pybmf_source_binop_ident_
    binop_bit_or_ident
    ___
    _left_name
    '|'
    _right_name
    __
    pybmf_emit_binop_bit_or
    __
    pybmf_source_binop_ident_
    binop_bit_and_ident
    ___
    _left_name
    '&'
    _right_name
    __
    pybmf_emit_binop_bit_and
    __
    pybmf_source_binop_ident_
    binop_bit_xor_ident
    ___
    _left_name
    '^'
    _right_name
    __
    pybmf_emit_binop_bit_xor
    __
    pybmf_source_binop_ident_
    binop_lshift_ident
    ___
    _left_name
    '<<'
    _right_name
    __
    pybmf_emit_binop_lshift
    __
    pybmf_source_binop_ident_
    binop_rshift_ident
    ___
    _left_name
    '>>'
    _right_name
    __
    pybmf_emit_binop_rshift
    __
    pybmf_source_binop_ident_
    bool_and_ident
    ___
    _left_name
    'and'
    _right_name
    __
    pybmf_emit_bool_and_
    bool_or_ident
    ___
    _left_name
    'or'
    _right_name
    __
    pybmf_emit_bool_or_
    lambda1_ident
    ___
    'lambda'
    _arg_name
    ':'
    _value_name
    __
    pybmf_emit_lambda1_ident
    __
    pybmf_source_lambda1_ident_
    await_ident
    ___
    'await'
    _value_name
    __
    pybmf_emit_await
    __
    pybmf_source_await_
    yield_ident
    ___
    'yield'
    _value_name
    __
    pybmf_emit_yield
    __
    pybmf_source_yield_
    yield_from_ident
    ___
    'yield'
    'from'
    _value_name
    __
    pybmf_emit_yield_from_
    match_header
    ___
    'match'
    _subject_name
    ':'
    __
    pybmf_emit_match_header
    __
    pybmf_source_match_header_
    case_pass
    ___
    'case'
    _pattern_name
    ':'
    'pass'
    __
    pybmf_emit_case_pass
    __
    pybmf_source_case_pass_
    case_guard_pass
    ___
    'case'
    _pattern_name
    'if'
    _guard_name
    ':'
    'pass'
    __
    pybmf_emit_case_guard_pass
    __
    pybmf_source_case_guard_pass_
    match_as
    ___
    _name_name
    'as'
    _alias_name
    __
    pybmf_emit_match_as
    __
    pybmf_source_match_as_
    float
    ___
    _value_float
    __
    pybmf_emit_float_
    bytes
    ___
    _value_bytes
    __
    pybmf_emit_bytes
    __
    pybmf_source_bytes_
    fstring
    ___
    _value_fstring
    __
    pybmf_emit_fstring
    __
    pybmf_source_fstring_
    fstring_format
    ___
    _prefix_fstring
    '{'
    _value_name
    '}'
    __
    pybmf_emit_fstring_format
    __
    pybmf_source_fstring_format_
    ellipsis
    ___
    '...'
    __
    pybmf_emit_ellipsis
    __
    pybmf_source_ellipsis_
    sample_module
    ___
    'import'
    _import_a_name
    'import'
    _import_b_name
    'from'
    _from_mod_name
    'import'
    _from_name_name
    _const_name_name
    '='
    _const_value_int
    'def'
    _add_name_name
    '('
    _add_a_name
    ','
    _add_b_name
    ')'
    ':'
    'return'
    _ret_left_name
    '+'
    _ret_right_name
    'def'
    _main_name_name
    '('
    ')'
    ':'
    _x_name_name
    '='
    _x_value_int
    _y_name_name
    '='
    _y_value_int
    _z_name_name
    '='
    _z_call_name
    '('
    _z_arg_a_name
    ','
    _z_arg_b_name
    ')'
    _print_call_name
    '('
    _print_arg_name
    ')'
    __
    pybmf_emit_sample_module_
    int
    ___
    _value_int
    __
    pybmf_emit_int_
    string
    ___
    _value_string
    __
    pybmf_emit_string_
    ident
    ___
    _value_name
    __
    pybmf_emit_ident_
    _
    pass
