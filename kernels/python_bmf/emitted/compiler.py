"""Emitted from Form source by kernels/python_bmf/emit_python.py."""
from kernels.python_bmf.host_primitives import *  # noqa: F401, F403

def compiler_object(kind, value, source, inverse):
    return cell(kind, value, source, inverse)

def is_compiler_object(x):
    return is_cell(x)

def compiler_object_kind(x):
    return cell_kind(x)

def compiler_object_value(x):
    return cell_value(x)

def compiler_object_source(x):
    return cell_origin(x)

def compiler_undo(x):
    return cell_undo(x)

def compiler_identity_inverse(x):
    return cell_origin(x)

def compiler_unit(language, name, sections):
    return compiler_object('compiler-unit', [language, name, sections], sections, compiler_identity_inverse)

def compiler_unit_language(x):
    return cell_value(x)[0]

def compiler_unit_name(x):
    return cell_value(x)[1]

def compiler_unit_sections(x):
    return cell_value(x)[2]

def compiler_section(language, name, items):
    return compiler_object('compiler-section', [language, name, items], items, compiler_identity_inverse)

def compiler_section_language(x):
    return cell_value(x)[0]

def compiler_section_name(x):
    return cell_value(x)[1]

def compiler_section_items(x):
    return cell_value(x)[2]

def compiler_rule(language, name, pattern, action):
    return compiler_object('compiler-rule', [language, name, pattern, action], pattern, compiler_identity_inverse)

def compiler_rule_language(x):
    return cell_value(x)[0]

def compiler_rule_name(x):
    return cell_value(x)[1]

def compiler_rule_pattern(x):
    return cell_value(x)[2]

def compiler_rule_action(x):
    return cell_value(x)[3]

def form_source(name, sections):
    return compiler_object('form-source', [name, sections], sections, compiler_identity_inverse)

def form_source_name(src):
    return cell_value(src)[0]

def form_source_sections(src):
    return cell_value(src)[1]

def form_source_section_by_dialect_list(sections, dialect):
    while True:
        if is_nil(sections):
            return empty()
        else:
            if str_eq(form_section_dialect(sections[0]), dialect):
                return sections[0]
            else:
                sections, dialect = sections[1:], dialect
                continue

def form_source_section_by_dialect(src, dialect):
    return form_source_section_by_dialect_list(form_source_sections(src), dialect)

def form_bmf_second(language, section_object):
    return form_section(str_concat(language, '.bmf'), section_object)

def form_rule_recipe_section(language, rules):
    return form_section(str_concat(language, '.recipes'), compiler_section(language, 'recipes', rules))

def comp_bmf_rule(name, args, item, process):
    return ['comp-bmf-rule', name, args, item, process]

def comp_bmf_sequence(items):
    return ['comp-bmf-sequence', items]

def comp_bmf_branch(items):
    return ['comp-bmf-branch', items]

def comp_bmf_repeat(item, min, max):
    return ['comp-bmf-repeat', item, min, max]

def comp_bmf_tag(name, item):
    return ['comp-bmf-tag', name, item]

def comp_bmf_rule_call(name, args):
    return ['comp-bmf-rule-call', name, args]

def comp_bmf_method_call(name, args):
    return ['comp-bmf-method-call', name, args]

def comp_bmf_primitive(name, args):
    return ['comp-bmf-primitive', name, args]

def comp_bmf_char_range(first, last):
    return ['comp-bmf-char-range', first, last]

def comp_bmf_char_chain(value):
    return ['comp-bmf-char-chain', value]

def comp_bmf_char_chain_strip(value, strip_before, strip_after):
    return ['comp-bmf-char-chain', value, strip_before, strip_after]

def comp_bmf_inline(item):
    return ['comp-bmf-inline', item]

def comp_bmf_literal(kind, value):
    return ['comp-bmf-literal', kind, value]

def comp_bmf_char(value):
    return ['comp-bmf-char', value]

def comp_bmf_process(code, result_type):
    return ['comp-bmf-process', code, result_type]

def comp_bmf_attribute(fields, code):
    return ['comp-bmf-attribute', fields, code]

def comp_bmf_syntax(name, extension, goal, rules, methods, primitives):
    return ['comp-bmf-syntax', name, extension, goal, rules, methods, primitives]

def comp_bmf_call_name(call):
    return call[1]

def comp_bmf_call_args(call):
    return call[2]

def bmf_src_name(value):
    return bmf_atom('bmf-name', value)

def bmf_src_string(value):
    return bmf_atom('bmf-string', value)

def bmf_src_char(value):
    return bmf_atom('bmf-char', value)

def bmf_src_int(value):
    return bmf_atom('bmf-int', value)

def bmf_src_float(value):
    return bmf_atom('bmf-float', value)

def bmf_src_field(value):
    return bmf_atom('bmf-field', value)

def bmf_src_args(value):
    return bmf_atom('bmf-args', value)

def bmf_src_fields(value):
    return bmf_atom('bmf-fields', value)

def bmf_src_code(value):
    return bmf_atom('bmf-code', value)

def bmf_src_op(value):
    return bmf_atom('bmf-op', value)

def bmf_kw(value):
    return object_lit('bmf-keyword', value)

def bmf_op(value):
    return object_lit('bmf-op', value)

def bmf_ref(name):
    return object_lit('bmf-ref', name)

def bmf_name(capture_name):
    return ['capture', capture_name, object_lit('bmf-name', '')]

def bmf_string_lit(capture_name):
    return ['capture', capture_name, object_lit('bmf-string', '')]

def bmf_pattern_lit(capture_name):
    return ['capture', capture_name, object_lit('bmf-pattern', '')]

def bmf_rules_lit(capture_name):
    return ['capture', capture_name, object_lit('bmf-rules', '')]

def bmf_meta_cap(objects, capture_name):
    return bmf_collection_value(objects, capture_name)

def bmf_emit_rule_source(objects):
    return bmf_rule_spec(bmf_meta_cap(objects, 'name'), bmf_meta_cap(objects, 'pattern'), bmf_meta_cap(objects, 'action'))

def bmf_emit_reversible_rule_source(objects):
    return bmf_reversible_rule_spec(bmf_meta_cap(objects, 'name'), bmf_meta_cap(objects, 'pattern'), bmf_meta_cap(objects, 'action'), bmf_meta_cap(objects, 'reverse'))

def bmf_emit_literal_source(objects):
    return bmf_terminal(bmf_meta_cap(objects, 'value'))

def bmf_emit_capture_source(objects):
    return bmf_capture(bmf_meta_cap(objects, 'name'), bmf_meta_cap(objects, 'kind'))

def bmf_emit_section_source(objects):
    return bmf_section(bmf_meta_cap(objects, 'dialect'), bmf_meta_cap(objects, 'rules'))

def bmf_emit_node_source(objects):
    return compiler_object('bmf-source-node', objects, objects, compiler_identity_inverse)

def bmf_compile_char_chain(objects):
    return comp_bmf_char_chain(bmf_meta_cap(objects, 'value'))

def bmf_compile_char_range(objects):
    return comp_bmf_char_range(bmf_meta_cap(objects, 'first'), bmf_meta_cap(objects, 'last'))

def bmf_compile_rule_call(objects):
    return comp_bmf_rule_call(bmf_meta_cap(objects, 'name'), empty())

def bmf_compile_primitive(objects):
    return comp_bmf_primitive(bmf_meta_cap(objects, 'name'), empty())

def bmf_compile_sequence_two(objects):
    return comp_bmf_sequence([bmf_meta_cap(objects, 'left'), bmf_meta_cap(objects, 'right')])

def bmf_compile_branch_two(objects):
    return comp_bmf_branch([bmf_meta_cap(objects, 'left'), bmf_meta_cap(objects, 'right')])

def bmf_compile_repeat_zero(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'item'), 0, 2147483647)

def bmf_compile_repeat_one(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'item'), 1, 2147483647)

def bmf_compile_optional(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'item'), 0, 1)

def bmf_compile_tag(objects):
    return comp_bmf_tag(bmf_meta_cap(objects, 'name'), bmf_meta_cap(objects, 'item'))

def bmf_compile_method_call(objects):
    call = bmf_meta_cap(objects, 'call')
    return comp_bmf_method_call(comp_bmf_call_name(call), comp_bmf_call_args(call))

def bmf_compile_rule(objects):
    call = bmf_meta_cap(objects, 'call')
    return comp_bmf_rule(comp_bmf_call_name(call), comp_bmf_call_args(call), bmf_meta_cap(objects, 'item'), empty())

def bmf_compile_bmf_char_int(objects):
    return comp_bmf_char(bmf_meta_cap(objects, 'value'))

def bmf_compile_bmf_char_quoted(objects):
    return comp_bmf_char(bmf_meta_cap(objects, 'value'))

def bmf_char_compiled_value(compiled_char):
    return compiled_char[1]

def bmf_compile_bmf_lit(objects):
    return comp_bmf_char_chain_strip(bmf_meta_cap(objects, 'value'), bmf_meta_cap(objects, 'strip-before'), bmf_meta_cap(objects, 'strip-after'))

def bmf_compile_bmf_range_single(objects):
    first = bmf_meta_cap(objects, 'first')
    return comp_bmf_char_range(bmf_char_compiled_value(first), bmf_char_compiled_value(first))

def bmf_compile_bmf_range(objects):
    return comp_bmf_char_range(bmf_char_compiled_value(bmf_meta_cap(objects, 'first')), bmf_char_compiled_value(bmf_meta_cap(objects, 'last')))

def bmf_compile_bmf_literal_int(objects):
    return comp_bmf_literal('int', bmf_meta_cap(objects, 'value'))

def bmf_compile_bmf_literal_float(objects):
    return comp_bmf_literal('float', bmf_meta_cap(objects, 'value'))

def bmf_compile_bmf_literal_string(objects):
    return comp_bmf_literal('string', bmf_meta_cap(objects, 'value'))

def bmf_compile_bmf_literal_field(objects):
    return comp_bmf_literal('field', bmf_meta_cap(objects, 'value'))

def bmf_compile_bmf_call(objects):
    return comp_bmf_rule_call(bmf_meta_cap(objects, 'name'), bmf_meta_cap(objects, 'args'))

def bmf_compile_bmf_call_base(objects):
    return bmf_meta_cap(objects, 'call')

def bmf_compile_bmf_inline(objects):
    return comp_bmf_inline(bmf_meta_cap(objects, 'expr'))

def bmf_compile_bmf_tag_named(objects):
    return comp_bmf_tag(bmf_meta_cap(objects, 'name'), empty())

def bmf_compile_bmf_tag_anon(_objects):
    return comp_bmf_tag('', empty())

def bmf_compile_bmf_expr_one(objects):
    return bmf_meta_cap(objects, 'term')

def bmf_compile_bmf_expr_branch(objects):
    return comp_bmf_branch([bmf_meta_cap(objects, 'left'), bmf_meta_cap(objects, 'right')])

def bmf_compile_bmf_term_one(objects):
    return bmf_meta_cap(objects, 'factor')

def bmf_compile_bmf_term_sequence(objects):
    return comp_bmf_sequence([bmf_meta_cap(objects, 'left'), bmf_meta_cap(objects, 'right')])

def bmf_compile_bmf_factor_item(objects):
    return bmf_meta_cap(objects, 'item')

def bmf_compile_bmf_factor_call(objects):
    return bmf_meta_cap(objects, 'call')

def bmf_compile_bmf_factor_tag_item(objects):
    return comp_bmf_tag(bmf_meta_cap(objects, 'tag')[1], bmf_meta_cap(objects, 'item'))

def bmf_compile_bmf_item_method_bare(objects):
    return bmf_meta_cap(objects, 'item')

def bmf_compile_bmf_item_method(objects):
    call = bmf_meta_cap(objects, 'call')
    return comp_bmf_method_call(comp_bmf_call_name(call), comp_bmf_call_args(call))

def bmf_compile_bmf_item_bare(objects):
    return bmf_meta_cap(objects, 'item')

def bmf_compile_bmf_item_star(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'item'), 0, 2147483647)

def bmf_compile_bmf_item_plus(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'item'), 1, 2147483647)

def bmf_compile_bmf_item_slash(objects):
    return comp_bmf_sequence([comp_bmf_repeat(bmf_meta_cap(objects, 'item'), (1 if str_eq(bmf_meta_cap(objects, 'mode'), '+') else 0), 2147483647), bmf_meta_cap(objects, 'next')])

def bmf_compile_bmf_opt(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'expr'), 0, 1)

def bmf_compile_bmf_must(objects):
    return comp_bmf_repeat(bmf_meta_cap(objects, 'expr'), str_to_int(bmf_meta_cap(objects, 'low')), str_to_int(bmf_meta_cap(objects, 'high')))

def bmf_compile_bmf_attribute(objects):
    return comp_bmf_attribute(bmf_meta_cap(objects, 'fields'), bmf_meta_cap(objects, 'code'))

def bmf_compile_bmf_rule_full(objects):
    call = bmf_meta_cap(objects, 'call')
    return comp_bmf_rule(comp_bmf_call_name(call), comp_bmf_call_args(call), bmf_meta_cap(objects, 'item'), empty())

def bmf_compiler_rule_name(r):
    return r[0]

def bmf_compiler_find_rule(rule_name, rules):
    while True:
        if is_nil(rules):
            return empty()
        else:
            if str_eq(bmf_compiler_rule_name(rules[0]), rule_name):
                return rules[0]
            else:
                rule_name, rules = rule_name, rules[1:]
                continue

def is_bmf_compiler_has_rule(rule_name):
    if is_nil(bmf_compiler_find_rule(rule_name, bmf_compiler_rules)):
        return False
    else:
        return True

def bmf_reference_covered_count_loop(names):
    if is_nil(names):
        return 0
    else:
        return ((1 if is_bmf_compiler_has_rule(names[0]) else 0) + bmf_reference_covered_count_loop(names[1:]))

def bmf_reference_covered_count(_x):
    return bmf_reference_covered_count_loop(bmf_reference_rule_names)

def apply_bmf_compiler_rule(rule_name, objects):
    return apply_object_rule(bmf_compiler_find_rule(rule_name, bmf_compiler_rules), objects)

def comp_op(name, value, inverse):
    return compiler_object('compiler-op', [name, value], value, inverse)

def comp_op_name(op):
    return cell_value(op)[0]

def comp_op_value(op):
    return cell_value(op)[1]

def comp_op_identity_inverse(op):
    return cell_origin(op)

def comp_program(language, ops):
    return compiler_object('compiler-program', [language, ops], ops, compiler_identity_inverse)

def comp_program_language(p):
    return cell_value(p)[0]

def comp_program_ops(p):
    return cell_value(p)[1]

def comp_vm_state(stack, snapshots, mode):
    return ['comp-vm-state', stack, snapshots, mode]

def comp_vm_stack(s):
    return s[1]

def comp_vm_snapshots(s):
    return s[2]

def comp_vm_mode(s):
    return s[3]

def comp_vm_with_stack(s, stack):
    return comp_vm_state(stack, comp_vm_snapshots(s), comp_vm_mode(s))

def comp_vm_with_snapshots(s, snapshots):
    return comp_vm_state(comp_vm_stack(s), snapshots, comp_vm_mode(s))

def comp_vm_with_mode(s, mode):
    return comp_vm_state(comp_vm_stack(s), comp_vm_snapshots(s), mode)

def comp_vm_push(s, value):
    return comp_vm_with_stack(s, [value, *comp_vm_stack(s)])

def comp_vm_pop_value(s):
    return comp_vm_stack(s)[0]

def comp_vm_pop_state(s):
    return comp_vm_with_stack(s, comp_vm_stack(s)[1:])

def comp_vm_save(s):
    return comp_vm_with_snapshots(s, [comp_vm_stack(s), *comp_vm_snapshots(s)])

def comp_vm_restore(s):
    return comp_vm_state(comp_vm_snapshots(s)[0], comp_vm_snapshots(s)[1:], comp_vm_mode(s))

def comp_vm_discard(s):
    return comp_vm_with_snapshots(s, comp_vm_snapshots(s)[1:])

def comp_vm_empty(_x):
    return comp_vm_state(empty(), empty(), 'run')

bmf_compiler_rules = [['char-chain', ['capture', 'value', object_lit('bmf-string', '')], bmf_compile_char_chain, bmf_identity_inverse], ['char-range', ['sequence', ['capture', 'first', object_lit('bmf-char', '')], bmf_op('..'), ['capture', 'last', object_lit('bmf-char', '')]], bmf_compile_char_range, bmf_identity_inverse], ['rule-call', ['capture', 'name', object_lit('bmf-name', '')], bmf_compile_rule_call, bmf_identity_inverse], ['primitive', ['sequence', bmf_op('<<prim'), ['capture', 'name', object_lit('bmf-name', '')], bmf_op('>>')], bmf_compile_primitive, bmf_identity_inverse], ['sequence-two', ['sequence', ['capture', 'left', object_lit('char-chain', '')], ['capture', 'right', object_lit('rule-call', '')]], bmf_compile_sequence_two, bmf_identity_inverse], ['branch-two', ['sequence', ['capture', 'left', object_lit('char-chain', '')], bmf_op('|'), ['capture', 'right', object_lit('rule-call', '')]], bmf_compile_branch_two, bmf_identity_inverse], ['repeat-zero', ['sequence', ['capture', 'item', object_lit('rule-call', '')], bmf_op('*')], bmf_compile_repeat_zero, bmf_identity_inverse], ['repeat-one', ['sequence', ['capture', 'item', object_lit('rule-call', '')], bmf_op('+')], bmf_compile_repeat_one, bmf_identity_inverse], ['optional', ['sequence', bmf_op('['), ['capture', 'item', object_lit('rule-call', '')], bmf_op(']')], bmf_compile_optional, bmf_identity_inverse], ['tag', ['sequence', bmf_op('$'), ['capture', 'name', object_lit('bmf-name', '')], bmf_op(':'), ['capture', 'item', object_lit('rule-call', '')]], bmf_compile_tag, bmf_identity_inverse], ['method-call', ['sequence', ['capture', 'item', object_lit('rule-call', '')], bmf_op('.'), ['capture', 'call', object_lit('rule-call', '')]], bmf_compile_method_call, bmf_identity_inverse], ['rule', ['sequence', ['capture', 'call', object_lit('rule-call', '')], bmf_op('::='), ['capture', 'item', object_lit('sequence-two', '')], bmf_op(';')], bmf_compile_rule, bmf_identity_inverse], ['BMFChar-int', ['sequence', bmf_op('\\'), ['capture', 'value', object_lit('bmf-int', '')]], bmf_compile_bmf_char_int, bmf_identity_inverse], ['BMFChar-quoted', ['sequence', bmf_op("'"), ['capture', 'value', object_lit('bmf-char', '')], bmf_op("'")], bmf_compile_bmf_char_quoted, bmf_identity_inverse], ['BMFLit', ['sequence', ['capture', 'strip-before', object_lit('bmf-int', '')], ['capture', 'value', object_lit('bmf-string', '')], ['capture', 'strip-after', object_lit('bmf-int', '')]], bmf_compile_bmf_lit, bmf_identity_inverse], ['BMFRange-single', ['capture', 'first', object_lit('BMFChar-int', '')], bmf_compile_bmf_range_single, bmf_identity_inverse], ['BMFRange', ['sequence', ['capture', 'first', object_lit('BMFChar-quoted', '')], bmf_op('..'), ['capture', 'last', object_lit('BMFChar-quoted', '')]], bmf_compile_bmf_range, bmf_identity_inverse], ['BMFBasis-range', ['capture', 'item', object_lit('BMFRange', '')], bmf_compile_bmf_item_bare, bmf_identity_inverse], ['BMFBasis-lit', ['capture', 'item', object_lit('BMFLit', '')], bmf_compile_bmf_item_bare, bmf_identity_inverse], ['BMFBasis-call', ['capture', 'item', object_lit('BMFCallBase', '')], bmf_compile_bmf_item_bare, bmf_identity_inverse], ['BMFLiteral-int', ['capture', 'value', object_lit('bmf-int', '')], bmf_compile_bmf_literal_int, bmf_identity_inverse], ['BMFLiteral-float', ['capture', 'value', object_lit('bmf-float', '')], bmf_compile_bmf_literal_float, bmf_identity_inverse], ['BMFLiteral-string', ['capture', 'value', object_lit('bmf-string', '')], bmf_compile_bmf_literal_string, bmf_identity_inverse], ['BMFLiteral-field', ['sequence', bmf_op('#'), ['capture', 'value', object_lit('bmf-field', '')]], bmf_compile_bmf_literal_field, bmf_identity_inverse], ['BMFCall', ['sequence', ['capture', 'name', object_lit('bmf-name', '')], ['capture', 'args', object_lit('bmf-args', '')]], bmf_compile_bmf_call, bmf_identity_inverse], ['BMFCallBase', ['capture', 'call', object_lit('BMFCall', '')], bmf_compile_bmf_call_base, bmf_identity_inverse], ['BMFPrim', ['sequence', bmf_op('<<prim'), ['capture', 'name', object_lit('bmf-name', '')], bmf_op('>>')], bmf_compile_primitive, bmf_identity_inverse], ['BMFInline', ['sequence', bmf_op('<<'), ['capture', 'expr', object_lit('BMFExpr', '')], bmf_op('>>')], bmf_compile_bmf_inline, bmf_identity_inverse], ['BMFTag', ['sequence', bmf_op('$'), ['capture', 'name', object_lit('bmf-name', '')], bmf_op(':')], bmf_compile_bmf_tag_named, bmf_identity_inverse], ['BMFTag-anon', bmf_op(':'), bmf_compile_bmf_tag_anon, bmf_identity_inverse], ['BMFExpr-one', ['capture', 'term', ['choice', object_lit('BMFTerm', ''), object_lit('BMFTerm-one', '')]], bmf_compile_bmf_expr_one, bmf_identity_inverse], ['BMFExpr', ['sequence', ['capture', 'left', ['choice', object_lit('BMFTerm', ''), object_lit('BMFTerm-one', '')]], bmf_op('|'), ['capture', 'right', ['choice', object_lit('BMFTerm', ''), object_lit('BMFTerm-one', '')]]], bmf_compile_bmf_expr_branch, bmf_identity_inverse], ['BMFTerm-one', ['capture', 'factor', object_lit('BMFFactor', '')], bmf_compile_bmf_term_one, bmf_identity_inverse], ['BMFTerm', ['sequence', ['capture', 'left', ['choice', object_lit('BMFFactor', ''), object_lit('BMFFactor-call', ''), object_lit('BMFFactor-tag', '')]], ['capture', 'right', ['choice', object_lit('BMFFactor', ''), object_lit('BMFFactor-call', ''), object_lit('BMFFactor-tag', '')]]], bmf_compile_bmf_term_sequence, bmf_identity_inverse], ['BMFFactor', ['capture', 'item', object_lit('BMFItemMethod', '')], bmf_compile_bmf_factor_item, bmf_identity_inverse], ['BMFFactor-call', ['sequence', bmf_op('@'), ['capture', 'call', object_lit('BMFCallBase', '')]], bmf_compile_bmf_factor_call, bmf_identity_inverse], ['BMFFactor-tag', ['sequence', ['capture', 'tag', object_lit('BMFTag', '')], ['capture', 'item', object_lit('BMFItemMethod', '')]], bmf_compile_bmf_factor_tag_item, bmf_identity_inverse], ['BMFItemMethod', ['capture', 'item', object_lit('BMFItem', '')], bmf_compile_bmf_item_method_bare, bmf_identity_inverse], ['BMFItemMethod-call', ['sequence', ['capture', 'item', object_lit('BMFItem', '')], bmf_op('.'), ['capture', 'call', object_lit('BMFCallBase', '')]], bmf_compile_bmf_item_method, bmf_identity_inverse], ['BMFItem', ['capture', 'item', object_lit('BMFBasis-lit', '')], bmf_compile_bmf_item_bare, bmf_identity_inverse], ['BMFItem-opt', ['capture', 'item', object_lit('BMFOpt', '')], bmf_compile_bmf_item_bare, bmf_identity_inverse], ['BMFItem-must', ['capture', 'item', object_lit('BMFMust', '')], bmf_compile_bmf_item_bare, bmf_identity_inverse], ['BMFItem-star', ['sequence', ['capture', 'item', object_lit('BMFBasis-call', '')], bmf_op('*')], bmf_compile_bmf_item_star, bmf_identity_inverse], ['BMFItem-plus', ['sequence', ['capture', 'item', object_lit('BMFBasis-call', '')], bmf_op('+')], bmf_compile_bmf_item_plus, bmf_identity_inverse], ['BMFItem-slash', ['sequence', ['capture', 'item', object_lit('BMFBasis-call', '')], bmf_op('\\'), ['capture', 'mode', object_lit('bmf-op', '')], ['capture', 'next', object_lit('BMFItem', '')]], bmf_compile_bmf_item_slash, bmf_identity_inverse], ['BMFOpt', ['sequence', bmf_op('['), ['capture', 'expr', object_lit('BMFExpr-one', '')], bmf_op(']')], bmf_compile_bmf_opt, bmf_identity_inverse], ['BMFMust', ['sequence', ['capture', 'low', object_lit('bmf-int', '')], bmf_op('('), ['capture', 'expr', object_lit('BMFExpr-one', '')], bmf_op(')'), ['capture', 'high', object_lit('bmf-int', '')]], bmf_compile_bmf_must, bmf_identity_inverse], ['BMFAttribute', ['sequence', ['capture', 'fields', object_lit('bmf-fields', '')], ['capture', 'code', object_lit('bmf-code', '')]], bmf_compile_bmf_attribute, bmf_identity_inverse], ['BMFRule', ['sequence', ['capture', 'call', object_lit('BMFCall', '')], bmf_op('::='), ['capture', 'item', ['choice', object_lit('BMFPrim', ''), object_lit('BMFInline', ''), object_lit('BMFExpr', ''), object_lit('BMFExpr-one', '')]], bmf_op(';')], bmf_compile_bmf_rule_full, bmf_identity_inverse]]
bmf_reference_rule_names = ['BMFRule', 'BMFLit', 'BMFRange', 'BMFChar-int', 'BMFChar-quoted', 'BMFBasis-range', 'BMFBasis-lit', 'BMFBasis-call', 'BMFLiteral-int', 'BMFLiteral-float', 'BMFLiteral-string', 'BMFLiteral-field', 'BMFCall', 'BMFCallBase', 'BMFPrim', 'BMFInline', 'BMFTag', 'BMFTag-anon', 'BMFExpr', 'BMFExpr-one', 'BMFTerm', 'BMFTerm-one', 'BMFFactor', 'BMFFactor-call', 'BMFFactor-tag', 'BMFItemMethod', 'BMFItemMethod-call', 'BMFItem', 'BMFItem-opt', 'BMFItem-must', 'BMFItem-star', 'BMFItem-plus', 'BMFItem-slash', 'BMFOpt', 'BMFMust', 'BMFAttribute']
bmf_bmf_rules = [['rule-reversible', ['sequence', bmf_name('name'), bmf_op('::='), bmf_pattern_lit('pattern'), bmf_op('=>'), bmf_name('action'), bmf_op('<='), bmf_name('reverse'), bmf_op(';')], bmf_emit_reversible_rule_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['rule', ['sequence', bmf_name('name'), bmf_op('::='), bmf_pattern_lit('pattern'), bmf_op('=>'), bmf_name('action'), bmf_op(';')], bmf_emit_rule_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['literal', ['sequence', bmf_string_lit('value')], bmf_emit_literal_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['capture', ['sequence', bmf_op('$'), bmf_name('name'), bmf_op(':'), bmf_name('kind')], bmf_emit_capture_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['section', ['sequence', bmf_kw('section'), bmf_op('['), bmf_name('dialect'), bmf_op(']'), bmf_op('{'), bmf_rules_lit('rules'), bmf_op('}')], bmf_emit_section_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-rule', ['sequence', bmf_ref('bmf-call'), bmf_op('::='), bmf_ref('bmf-rule-body'), bmf_op(';'), bmf_ref('cut')], bmf_emit_rule_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-rule-body', ['sequence', bmf_ref('bmf-prim'), bmf_op('|'), bmf_ref('bmf-inline'), bmf_op('|'), bmf_ref('bmf-expr')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-lit', ['sequence', bmf_ref('bmf-bang-prefix'), bmf_ref('string'), bmf_ref('bmf-bang-suffix')], bmf_emit_literal_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-range', ['sequence', bmf_ref('bmf-char'), bmf_op('..'), bmf_ref('bmf-char')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-range-single', ['sequence', bmf_ref('bmf-char')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-char-int', ['sequence', bmf_op('\\\\'), bmf_ref('cut'), bmf_ref('int')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-char-quoted', ['sequence', bmf_op("'"), bmf_ref('cut'), bmf_ref('bmf-char-body'), bmf_op("'")], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-char-body', ['sequence', bmf_op('\\\\'), bmf_ref('bmf-escape-char'), bmf_op('|'), bmf_ref('char-range')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-basis', ['sequence', bmf_ref('bmf-range'), bmf_op('|'), bmf_ref('bmf-lit'), bmf_op('|'), bmf_ref('bmf-call-base')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-literal', ['sequence', bmf_ref('float'), bmf_op('|'), bmf_ref('int'), bmf_op('|'), bmf_ref('string'), bmf_op('|'), bmf_op('#'), bmf_ref('cut'), bmf_ref('field-name')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-call', ['sequence', bmf_name('base'), bmf_ref('bmf-call-args')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-call-args', ['sequence', bmf_op('('), bmf_ref('cut'), bmf_ref('bmf-arg-list'), bmf_op(')')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-call-base', ['sequence', bmf_ref('bmf-call')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-prim', ['sequence', bmf_op('<<prim'), bmf_ref('spc'), bmf_ref('id'), bmf_op('>>')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-inline', ['sequence', bmf_op('<<'), bmf_ref('bmf-expr'), bmf_op('>>')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-tag', ['sequence', bmf_op('$'), bmf_name('tag'), bmf_ref('cut'), bmf_op(':')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-anonymous-tag', ['sequence', bmf_op(':')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-expr', ['sequence', bmf_ref('bmf-term'), bmf_ref('bmf-expr-tail')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-expr-tail', ['sequence', bmf_op('|'), bmf_ref('bmf-term')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-term', ['sequence', bmf_ref('bmf-factor'), bmf_ref('bmf-term-tail')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-term-tail', ['sequence', bmf_ref('bmf-factor')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-factor', ['sequence', bmf_ref('bmf-tag'), bmf_ref('bmf-factor-body')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-factor-body', ['sequence', bmf_op('@'), bmf_ref('cut'), bmf_ref('bmf-call-base'), bmf_op('|'), bmf_ref('bmf-item-method')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-item-method', ['sequence', bmf_ref('bmf-item'), bmf_op('.'), bmf_ref('cut'), bmf_ref('bmf-call-base')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-item-method-bare', ['sequence', bmf_ref('bmf-item')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-item', ['sequence', bmf_ref('bmf-item-body'), bmf_ref('bmf-repeat-suffix')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-item-body', ['sequence', bmf_ref('bmf-opt'), bmf_op('|'), bmf_ref('bmf-basis'), bmf_op('|'), bmf_ref('bmf-must')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-repeat-suffix', ['sequence', bmf_op('*'), bmf_op('|'), bmf_op('+'), bmf_op('|'), bmf_op('\\\\'), bmf_ref('bmf-repeat-mode'), bmf_ref('bmf-item')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-repeat-mode', ['sequence', bmf_op('+'), bmf_op('|'), bmf_op('*'), bmf_op('|'), bmf_ref('nil')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-opt', ['sequence', bmf_op('['), bmf_ref('cut'), bmf_ref('bmf-expr'), bmf_op(']')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-must', ['sequence', bmf_ref('int'), bmf_op('('), bmf_ref('bmf-expr'), bmf_op(')'), bmf_ref('int')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter], ['bmf-attribute', ['sequence', bmf_ref('id-list'), bmf_ref('code-block')], bmf_emit_node_source, bmf_identity_inverse, bmf_default_reverse_emitter]]
bmf_bmf_second = form_bmf_second('bmf', bmf_section('bmf.bmf', bmf_bmf_rules))
bmf_recipe_section = form_rule_recipe_section('bmf', [compiler_rule('bmf', 'rule', 'BMF rule source objects', bmf_emit_rule_source), compiler_rule('bmf', 'literal', 'BMF literal source object', bmf_emit_literal_source), compiler_rule('bmf', 'capture', 'BMF capture source object', bmf_emit_capture_source), compiler_rule('bmf', 'section', 'BMF section source object', bmf_emit_section_source)])
bmf_form_source = form_source('bmf', [bmf_bmf_second, bmf_recipe_section])

if __name__ == '__main__':
    pass
