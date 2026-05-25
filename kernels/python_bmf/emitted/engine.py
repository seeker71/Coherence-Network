def cap_empty(_x):
    return empty()

def cap_pair(name, value):
    return [name, value]

def cap_name(p):
    return p[0]

def cap_value(p):
    return p[1:][0]

def cap_get(caps, name):
    if is_nil(caps):
        return empty()
    else:
        if str_eq(cap_name(caps[0]), name):
            return cap_value(caps[0])
        else:
            return cap_get(caps[1:], name)

def cap_set(caps, name, value):
    return [cap_pair(name, value), *caps]

def cap_merge(a, b):
    if is_nil(b):
        return a
    else:
        return cap_merge([b[0], *a], b[1:])

def mk_match(caps, rest):
    return ['match', caps, rest]

def mk_fail(reason):
    return ['fail', reason]

def is_match(r):
    return str_eq(r[0], 'match')

def is_fail(r):
    return str_eq(r[0], 'fail')

def match_caps(r):
    return r[1:][0]

def match_rest(r):
    return r[1:][1:][0]

def fail_reason(r):
    return r[1:][0]

def bmf_match_source(captures, span):
    return ['bmf-match-source', captures, span]

def is_bmf_match_source(source):
    return ((len(source) > 0) and str_eq(source[0], 'bmf-match-source'))

def bmf_match_source_captures(source):
    return source[1]

def bmf_match_source_span(source):
    return source[2]

def bmf_object(kind, value, source, inverse):
    return cell(kind, value, source, inverse)

def is_bmf_object(x):
    return is_cell(x)

def bmf_object_kind(o):
    return cell_kind(o)

def bmf_object_value(o):
    return cell_value(o)

def bmf_object_source(o):
    source = cell_origin(o)
    return (bmf_match_source_captures(source) if is_bmf_match_source(source) else source)

def bmf_object_source_span(o):
    source = cell_origin(o)
    return (bmf_match_source_span(source) if is_bmf_match_source(source) else bmf_collection_items(bmf_object_source(o)))

def bmf_object_inverse(o):
    return cell_inverse(o)

def bmf_symbol_binding(anchor, domain, lens, symbol, names):
    return ['bmf-symbol-binding', anchor, domain, lens, symbol, names]

def bmf_symbol_binding_anchor(binding):
    return binding[1]

def bmf_symbol_binding_domain(binding):
    return binding[2]

def bmf_symbol_binding_lens(binding):
    return binding[3]

def bmf_symbol_binding_symbol(binding):
    return binding[4]

def bmf_symbol_binding_names(binding):
    return binding[5]

def bmf_symbol_binding_name(binding):
    return bmf_symbol_binding_names(binding)[0]

def bmf_symbol_cell_undo(symbol_cell):
    return cell_origin(symbol_cell)

def bmf_global_symbol_cell(anchor, domain, lens, symbol, names, origin):
    return cell('bmf-symbol', bmf_symbol_binding(anchor, domain, lens, symbol, names), origin, bmf_symbol_cell_undo)

def bmf_symbol_cell_binding(symbol_cell):
    return cell_value(symbol_cell)

def bmf_lens_property(key, value):
    return ['bmf-lens-property', key, value]

def bmf_lens_property_key(property):
    return property[1]

def bmf_lens_property_value(property):
    return property[2]

def bmf_symbol_context(domain, lens, bindings):
    return ['bmf-symbol-context', domain, lens, bindings]

def bmf_symbol_context_for(domain, lens, bindings, properties):
    return ['bmf-symbol-context', domain, lens, bindings, properties]

def bmf_symbol_context_domain(ctx):
    return ctx[1]

def bmf_symbol_context_lens(ctx):
    return ctx[2]

def bmf_symbol_context_bindings(ctx):
    return ctx[3]

def bmf_symbol_context_properties(ctx):
    if (len(ctx) > 4):
        return ctx[4]
    else:
        return empty()

def bmf_symbol_context_property_loop(properties, key, missing):
    if is_nil(properties):
        return missing
    else:
        if str_eq(bmf_lens_property_key(properties[0]), key):
            return bmf_lens_property_value(properties[0])
        else:
            return bmf_symbol_context_property_loop(properties[1:], key, missing)

def bmf_symbol_context_property(ctx, key, missing):
    return bmf_symbol_context_property_loop(bmf_symbol_context_properties(ctx), key, missing)

def bmf_domain_ref(index):
    return intern_node(BMF_DOMAIN_REF, [intern_trivial_int(index)])

def bmf_lens_ref(index):
    return intern_node(BMF_LENS_REF, [intern_trivial_int(index)])

def bmf_domain_kind_ref(index):
    return intern_node(BMF_DOMAIN_KIND_REF, [intern_trivial_int(index)])

def bmf_surface_ref(index):
    return intern_node(BMF_SURFACE_REF, [intern_trivial_int(index)])

def bmf_domain_python():
    return bmf_domain_ref(1)

def bmf_domain_typescript():
    return bmf_domain_ref(2)

def bmf_domain_go():
    return bmf_domain_ref(3)

def bmf_domain_rust():
    return bmf_domain_ref(4)

def bmf_domain_bml():
    return bmf_domain_ref(5)

def bmf_domain_natural():
    return bmf_domain_ref(6)

def bmf_domain_image():
    return bmf_domain_ref(7)

def bmf_domain_audio():
    return bmf_domain_ref(8)

def bmf_domain_video():
    return bmf_domain_ref(9)

def bmf_domain_kind_language():
    return bmf_domain_kind_ref(1)

def bmf_domain_kind_media():
    return bmf_domain_kind_ref(2)

def bmf_domain_kind_runtime():
    return bmf_domain_kind_ref(3)

def bmf_semantic_natural_language():
    return 'natural-language'

def bmf_semantic_image():
    return 'image'

def bmf_semantic_audio():
    return 'audio'

def bmf_semantic_video():
    return 'video'

def bmf_semantic_general():
    return 'general'

def bmf_semantic_knowledge():
    return 'knowledge'

def bmf_lens_assertion():
    return bmf_lens_ref(1)

def bmf_lens_metadata():
    return bmf_lens_ref(2)

def bmf_lens_assign():
    return bmf_lens_ref(3)

def bmf_lens_var():
    return bmf_lens_ref(4)

def bmf_lens_quote():
    return bmf_lens_ref(5)

def bmf_lens_display():
    return bmf_lens_ref(6)

def bmf_context_key_language_tag():
    return 'language-tag'

def bmf_context_key_locale():
    return 'locale'

def bmf_context_key_script():
    return 'script'

def bmf_context_key_region():
    return 'region'

def bmf_context_key_direction():
    return 'direction'

def bmf_context_key_calendar():
    return 'calendar'

def bmf_context_key_numbering_system():
    return 'numbering-system'

def bmf_context_key_time_zone():
    return 'time-zone'

def bmf_context_key_semantic_domain():
    return 'semantic-domain'

def bmf_context_key_culture():
    return 'culture'

def bmf_context_key_register():
    return 'register'

def bmf_context_key_environment():
    return 'environment'

def bmf_context_key_audience():
    return 'audience'

def bmf_context_key_purpose():
    return 'purpose'

def bmf_context_key_viewpoint():
    return 'viewpoint'

def bmf_context_key_media_type():
    return 'media-type'

def bmf_context_key_charset():
    return 'charset'

def bmf_context_key_encoding():
    return 'encoding'

def bmf_context_key_container():
    return 'container'

def bmf_context_key_codec():
    return 'codec'

def bmf_context_key_unit():
    return 'unit'

def bmf_context_key_color_space():
    return 'color-space'

def bmf_context_key_source():
    return 'source'

def bmf_context_key_creator():
    return 'creator'

def bmf_context_key_license():
    return 'license'

def bmf_context_key_created():
    return 'created'

def bmf_context_key_derived_from():
    return 'derived-from'

def bmf_locale_und():
    return 'und'

def bmf_locale_en_us():
    return 'en-US'

def bmf_locale_id_id():
    return 'id-ID'

def bmf_script_latn():
    return 'Latn'

def bmf_direction_auto():
    return 'auto'

def bmf_direction_ltr():
    return 'ltr'

def bmf_direction_rtl():
    return 'rtl'

def bmf_register_plain():
    return 'plain'

def bmf_register_math():
    return 'math'

def bmf_register_formal():
    return 'formal'

def bmf_environment_general():
    return 'general'

def bmf_environment_file():
    return 'file'

def bmf_environment_repo():
    return 'repo'

def bmf_environment_web():
    return 'web'

def bmf_purpose_representation():
    return 'representation'

def bmf_purpose_roundtrip():
    return 'roundtrip'

def bmf_calendar_gregory():
    return 'gregory'

def bmf_numbering_latn():
    return 'latn'

def bmf_media_text_plain():
    return 'text/plain'

def bmf_media_octet_stream():
    return 'application/octet-stream'

def bmf_media_image_svg():
    return 'image/svg+xml'

def bmf_media_image_gif():
    return 'image/gif'

def bmf_charset_utf8():
    return 'utf-8'

def bmf_encoding_xml():
    return 'xml'

def bmf_encoding_binary():
    return 'binary'

def bmf_container_text():
    return 'text'

def bmf_unit_px():
    return 'px'

def bmf_unit_samples():
    return 'samples'

def bmf_unit_px_ms():
    return 'px/ms'

def bmf_color_srgb():
    return 'sRGB'

def bmf_language_properties(language_tag, locale, script, region, direction, calendar, numbering_system, time_zone):
    return [bmf_lens_property(bmf_context_key_language_tag(), language_tag), bmf_lens_property(bmf_context_key_locale(), locale), bmf_lens_property(bmf_context_key_script(), script), bmf_lens_property(bmf_context_key_region(), region), bmf_lens_property(bmf_context_key_direction(), direction), bmf_lens_property(bmf_context_key_calendar(), calendar), bmf_lens_property(bmf_context_key_numbering_system(), numbering_system), bmf_lens_property(bmf_context_key_time_zone(), time_zone)]

def bmf_domain_properties(domain, culture, register, environment, audience, purpose, viewpoint):
    return [bmf_lens_property(bmf_context_key_semantic_domain(), domain), bmf_lens_property(bmf_context_key_culture(), culture), bmf_lens_property(bmf_context_key_register(), register), bmf_lens_property(bmf_context_key_environment(), environment), bmf_lens_property(bmf_context_key_audience(), audience), bmf_lens_property(bmf_context_key_purpose(), purpose), bmf_lens_property(bmf_context_key_viewpoint(), viewpoint)]

def bmf_media_properties(media_type, charset, encoding, container, codec, unit, color_space):
    return [bmf_lens_property(bmf_context_key_media_type(), media_type), bmf_lens_property(bmf_context_key_charset(), charset), bmf_lens_property(bmf_context_key_encoding(), encoding), bmf_lens_property(bmf_context_key_container(), container), bmf_lens_property(bmf_context_key_codec(), codec), bmf_lens_property(bmf_context_key_unit(), unit), bmf_lens_property(bmf_context_key_color_space(), color_space)]

def bmf_provenance_properties(source, creator, license, created, derived_from):
    return [bmf_lens_property(bmf_context_key_source(), source), bmf_lens_property(bmf_context_key_creator(), creator), bmf_lens_property(bmf_context_key_license(), license), bmf_lens_property(bmf_context_key_created(), created), bmf_lens_property(bmf_context_key_derived_from(), derived_from)]

def bmf_context_properties(language, domain, media, provenance):
    return append(language, append(domain, append(media, provenance)))

def bmf_standard_symbol_context(domain, lens, bindings, language_properties, domain_properties, media_properties, provenance_properties):
    return bmf_symbol_context_for(domain, lens, bindings, bmf_context_properties(language_properties, domain_properties, media_properties, provenance_properties))

def bmf_context_language_tag(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_language_tag(), bmf_locale_und())

def bmf_context_locale(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_locale(), bmf_locale_und())

def bmf_context_script(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_script(), '')

def bmf_context_region(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_region(), '')

def bmf_context_direction(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_direction(), bmf_direction_auto())

def bmf_context_calendar(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_calendar(), '')

def bmf_context_numbering_system(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_numbering_system(), '')

def bmf_context_time_zone(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_time_zone(), '')

def bmf_context_semantic_domain(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_semantic_domain(), bmf_semantic_general())

def bmf_context_culture(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_culture(), '')

def bmf_context_register(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_register(), bmf_register_plain())

def bmf_context_environment(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_environment(), bmf_environment_general())

def bmf_context_audience(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_audience(), '')

def bmf_context_purpose(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_purpose(), '')

def bmf_context_viewpoint(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_viewpoint(), '')

def bmf_context_media_type(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_media_type(), bmf_media_octet_stream())

def bmf_context_charset(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_charset(), '')

def bmf_context_encoding(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_encoding(), '')

def bmf_context_container(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_container(), '')

def bmf_context_codec(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_codec(), '')

def bmf_context_unit(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_unit(), '')

def bmf_context_color_space(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_color_space(), '')

def bmf_context_source(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_source(), '')

def bmf_context_creator(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_creator(), '')

def bmf_context_license(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_license(), '')

def bmf_context_created(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_created(), '')

def bmf_context_derived_from(ctx):
    return bmf_symbol_context_property(ctx, bmf_context_key_derived_from(), '')

def is_bmf_symbol_binding_matches(binding, ctx, anchor):
    return (str_eq(bmf_symbol_binding_anchor(binding), anchor) and (node_eq(bmf_symbol_binding_domain(binding), bmf_symbol_context_domain(ctx)) and node_eq(bmf_symbol_binding_lens(binding), bmf_symbol_context_lens(ctx))))

def is_bmf_symbol_name_in_list(names, name):
    if is_nil(names):
        return False
    else:
        if str_eq(names[0], name):
            return True
        else:
            return is_bmf_symbol_name_in_list(names[1:], name)

def is_bmf_symbol_binding_name_matches(binding, ctx, name):
    return (is_bmf_symbol_name_in_list(bmf_symbol_binding_names(binding), name) and (node_eq(bmf_symbol_binding_domain(binding), bmf_symbol_context_domain(ctx)) and node_eq(bmf_symbol_binding_lens(binding), bmf_symbol_context_lens(ctx))))

def bmf_symbol_find_loop(bindings, ctx, anchor, missing):
    if is_nil(bindings):
        return missing
    else:
        if is_bmf_symbol_binding_matches(bindings[0], ctx, anchor):
            return bindings[0]
        else:
            return bmf_symbol_find_loop(bindings[1:], ctx, anchor, missing)

def bmf_symbol_find(ctx, anchor, missing):
    return bmf_symbol_find_loop(bmf_symbol_context_bindings(ctx), ctx, anchor, missing)

def bmf_symbol_name(ctx, anchor, missing):
    binding = bmf_symbol_find(ctx, anchor, empty())
    return (missing if is_nil(binding) else bmf_symbol_binding_name(binding))

def bmf_symbol_value(ctx, anchor, missing):
    binding = bmf_symbol_find(ctx, anchor, empty())
    return (missing if is_nil(binding) else bmf_symbol_binding_symbol(binding))

def bmf_anchor_resolve_loop(bindings, ctx, name, missing):
    if is_nil(bindings):
        return missing
    else:
        if is_bmf_symbol_binding_name_matches(bindings[0], ctx, name):
            return bmf_symbol_binding_anchor(bindings[0])
        else:
            return bmf_anchor_resolve_loop(bindings[1:], ctx, name, missing)

def bmf_anchor_resolve(ctx, name, missing):
    return bmf_anchor_resolve_loop(bmf_symbol_context_bindings(ctx), ctx, name, missing)

def bmf_reverse_lens_node_from(domain, lens):
    return intern_node(BMF_REVERSE_LENS, [domain, lens])

def bmf_reverse_lens(domain, lens, emit, parse, rule):
    return [bmf_reverse_lens_node_from(domain, lens), domain, lens, emit, parse, rule]

def bmf_reverse_lens_for(domain, lens, emit, parse, rule, requirements):
    return [bmf_reverse_lens_node_from(domain, lens), domain, lens, emit, parse, rule, requirements]

def bmf_reverse_lens_domain(target):
    return target[1]

def bmf_reverse_lens_lens(target):
    return target[2]

def bmf_reverse_lens_emit(target):
    return target[3]

def bmf_reverse_lens_parse(target):
    return target[4]

def bmf_reverse_lens_rule(target):
    return target[5]

def bmf_reverse_lens_requirements(target):
    if (len(target) > 6):
        return target[6]
    else:
        return empty()

def bmf_contract_field(node, index):
    return node_children(node)[index]

def bmf_domain_contract_node_from(id, kind):
    return intern_node(BMF_DOMAIN_CONTRACT, [id, kind])

def bmf_domain_contract(id, kind, properties):
    return [bmf_domain_contract_node_from(id, kind), properties]

def bmf_domain_contract_node(domain):
    return domain[0]

def bmf_domain_contract_id(domain):
    return bmf_contract_field(bmf_domain_contract_node(domain), 0)

def bmf_domain_contract_kind(domain):
    return bmf_contract_field(bmf_domain_contract_node(domain), 1)

def bmf_domain_contract_properties(domain):
    return domain[1]

def bmf_surface_contract_node_from(id, domain, lens, media_type):
    return intern_node(BMF_SURFACE_CONTRACT, [id, domain, lens])

def bmf_surface_contract(id, domain, lens, media_type, context_requirements, rulebook, capabilities):
    return [bmf_surface_contract_node_from(id, domain, lens, media_type), context_requirements, rulebook, capabilities]

def bmf_surface_contract_node(surface):
    return surface[0]

def bmf_surface_contract_id(surface):
    return bmf_contract_field(bmf_surface_contract_node(surface), 0)

def bmf_surface_contract_domain(surface):
    return bmf_contract_field(bmf_surface_contract_node(surface), 1)

def bmf_surface_contract_lens(surface):
    return bmf_contract_field(bmf_surface_contract_node(surface), 2)

def bmf_surface_contract_media_type(surface):
    return empty()

def bmf_surface_contract_requirements(surface):
    return surface[1]

def bmf_surface_contract_rulebook(surface):
    return surface[2]

def bmf_surface_contract_capabilities(surface):
    return surface[3]

def bmf_lens_contract_node_from(surface):
    return intern_node(BMF_LENS_CONTRACT, [bmf_surface_contract_node(surface)])

def bmf_lens_contract(surface, emit, parse, rule):
    return [bmf_lens_contract_node_from(surface), surface, emit, parse, rule]

def bmf_lens_contract_node(contract):
    return contract[0]

def bmf_lens_contract_surface(contract):
    return contract[1]

def bmf_lens_contract_emit(contract):
    return contract[2]

def bmf_lens_contract_parse(contract):
    return contract[3]

def bmf_lens_contract_rule(contract):
    return contract[4]

def bmf_lens_contract_to_target(contract):
    surface = bmf_lens_contract_surface(contract)
    return bmf_reverse_lens_for(bmf_surface_contract_domain(surface), bmf_surface_contract_lens(surface), bmf_lens_contract_emit(contract), bmf_lens_contract_parse(contract), bmf_lens_contract_rule(contract), bmf_surface_contract_requirements(surface))

def bmf_lens_contracts_to_targets(contracts):
    if is_nil(contracts):
        return empty()
    else:
        return [bmf_lens_contract_to_target(contracts[0]), *bmf_lens_contracts_to_targets(contracts[1:])]

def bmf_translation_space_node_from(domains, surfaces, contracts):
    return intern_node(BMF_TRANSLATION_SPACE, [intern_trivial_int(len(domains)), intern_trivial_int(len(surfaces)), intern_trivial_int(len(contracts))])

def bmf_translation_space(domains, surfaces, contracts):
    return [bmf_translation_space_node_from(domains, surfaces, contracts), domains, surfaces, contracts]

def bmf_translation_space_node(space):
    return space[0]

def bmf_translation_space_domains(space):
    return space[1]

def bmf_translation_space_surfaces(space):
    return space[2]

def bmf_translation_space_contracts(space):
    return space[3]

def bmf_translation_space_targets(space):
    return bmf_lens_contracts_to_targets(bmf_translation_space_contracts(space))

def is_bmf_surface_contract_matches(surface, domain, lens):
    return (node_eq(bmf_surface_contract_domain(surface), domain) and node_eq(bmf_surface_contract_lens(surface), lens))

def bmf_surface_contract_score(surface, domain, lens, ctx):
    if is_bmf_surface_contract_matches(surface, domain, lens):
        return bmf_context_properties_score(ctx, bmf_surface_contract_requirements(surface))
    else:
        return (0 - 1)

def bmf_translation_space_find_surface_best(surfaces, domain, lens, ctx, best, best_score, missing):
    if is_nil(surfaces):
        return best
    else:
        score = bmf_surface_contract_score(surfaces[0], domain, lens, ctx)
        return (bmf_translation_space_find_surface_best(surfaces[1:], domain, lens, ctx, surfaces[0], score, missing) if (score > best_score) else bmf_translation_space_find_surface_best(surfaces[1:], domain, lens, ctx, best, best_score, missing))

def bmf_translation_space_find_surface(space, domain, lens, ctx, missing):
    return bmf_translation_space_find_surface_best(bmf_translation_space_surfaces(space), domain, lens, ctx, missing, (0 - 1), missing)

def bmf_translation_space_roundtrip(space, domain, lens, node, anchor, ctx, missing):
    return bmf_lens_roundtrip_for_context(bmf_translation_space_targets(space), domain, lens, node, anchor, ctx, missing)

def is_bmf_reverse_lens_matches(target, domain, lens):
    return (node_eq(bmf_reverse_lens_domain(target), domain) and node_eq(bmf_reverse_lens_lens(target), lens))

def bmf_reverse_lens_find(targets, domain, lens, missing):
    if is_nil(targets):
        return missing
    else:
        if is_bmf_reverse_lens_matches(targets[0], domain, lens):
            return targets[0]
        else:
            return bmf_reverse_lens_find(targets[1:], domain, lens, missing)

def form_capsule_root(package, level, type, instance):
    return intern_node(FORM_CAPSULE_ROOT, [intern_trivial_int(package), intern_trivial_int(level), intern_trivial_int(type), intern_trivial_int(instance)])

def form_dynamic_kind(root, local):
    return intern_node(FORM_DYNAMIC_KIND, [root, intern_trivial_int(local)])

def form_dynamic_ref(root, kind, local):
    return intern_node(FORM_DYNAMIC_REF, [root, kind, intern_trivial_int(local)])

def form_adapter_capability_node_from(kind, input_surface, output_surface):
    return intern_node(FORM_ADAPTER_CAPABILITY, [kind, input_surface, output_surface])

def form_adapter_capability(kind, input_surface, output_surface, emit, parse, rule, requirements):
    return [form_adapter_capability_node_from(kind, input_surface, output_surface), kind, input_surface, output_surface, emit, parse, rule, requirements]

def form_adapter_capability_node(capability):
    return capability[0]

def form_adapter_capability_kind(capability):
    return capability[1]

def form_adapter_capability_input_surface(capability):
    return capability[2]

def form_adapter_capability_output_surface(capability):
    return capability[3]

def form_adapter_capability_emit(capability):
    return capability[4]

def form_adapter_capability_parse(capability):
    return capability[5]

def form_adapter_capability_rule(capability):
    return capability[6]

def form_adapter_capability_requirements(capability):
    return capability[7]

def form_capability_contract_node_from(capability):
    return intern_node(FORM_CAPABILITY_CONTRACT, [form_adapter_capability_node(capability)])

def form_capability_contract(capability, effect, reversibility, lossiness, deterministic, resources):
    return [form_capability_contract_node_from(capability), capability, effect, reversibility, lossiness, deterministic, resources]

def form_capability_contract_node(contract):
    return contract[0]

def form_capability_contract_capability(contract):
    return contract[1]

def form_capability_contract_effect(contract):
    return contract[2]

def form_capability_contract_reversibility(contract):
    return contract[3]

def form_capability_contract_lossiness(contract):
    return contract[4]

def form_capability_contract_deterministic(contract):
    return contract[5]

def form_capability_contract_resources(contract):
    return contract[6]

def form_capability_contract_capability_node(contract):
    return form_adapter_capability_node(form_capability_contract_capability(contract))

def form_capability_cost_node_from(capability):
    return intern_node(FORM_CAPABILITY_COST, [form_adapter_capability_node(capability)])

def form_capability_cost(capability, total_walks, function_calls, native_calls, allocations, score):
    return [form_capability_cost_node_from(capability), capability, total_walks, function_calls, native_calls, allocations, score]

def form_capability_cost_node(cost):
    return cost[0]

def form_capability_cost_capability(cost):
    return cost[1]

def form_capability_cost_total_walks(cost):
    return cost[2]

def form_capability_cost_function_calls(cost):
    return cost[3]

def form_capability_cost_native_calls(cost):
    return cost[4]

def form_capability_cost_allocations(cost):
    return cost[5]

def form_capability_cost_score(cost):
    return cost[6]

def form_capability_cost_capability_node(cost):
    return form_adapter_capability_node(form_capability_cost_capability(cost))

def form_capability_proof_node_from(capability, proof_kind):
    return intern_node(FORM_CAPABILITY_PROOF, [form_adapter_capability_node(capability), proof_kind])

def form_capability_proof(capability, proof_kind, proof_recipe, expected):
    return [form_capability_proof_node_from(capability, proof_kind), capability, proof_kind, proof_recipe, expected]

def form_capability_proof_node(proof):
    return proof[0]

def form_capability_proof_capability(proof):
    return proof[1]

def form_capability_proof_kind(proof):
    return proof[2]

def form_capability_proof_recipe(proof):
    return proof[3]

def form_capability_proof_expected(proof):
    return proof[4]

def form_capability_specializer_node_from(capability, specializer_kind):
    return intern_node(FORM_CAPABILITY_SPECIALIZER, [form_adapter_capability_node(capability), specializer_kind])

def form_capability_specializer(capability, specializer_kind, specialize_recipe, requirements):
    return [form_capability_specializer_node_from(capability, specializer_kind), capability, specializer_kind, specialize_recipe, requirements]

def form_capability_specializer_node(specializer):
    return specializer[0]

def form_capability_specializer_capability(specializer):
    return specializer[1]

def form_capability_specializer_kind(specializer):
    return specializer[2]

def form_capability_specializer_recipe(specializer):
    return specializer[3]

def form_capability_specializer_requirements(specializer):
    return specializer[4]

def form_recipe_capsule_node_from(root, surfaces, capabilities, contracts, proofs, costs, specializers):
    return intern_node(FORM_RECIPE_CAPSULE, [root, intern_trivial_int(len(surfaces)), intern_trivial_int(len(capabilities)), intern_trivial_int(len(contracts)), intern_trivial_int(len(proofs)), intern_trivial_int(len(costs)), intern_trivial_int(len(specializers))])

def form_recipe_capsule(root, surfaces, capabilities, contracts, proofs, costs, specializers, symbol_packs):
    return [form_recipe_capsule_node_from(root, surfaces, capabilities, contracts, proofs, costs, specializers), root, surfaces, capabilities, contracts, proofs, costs, specializers, symbol_packs]

def form_recipe_capsule_node(capsule):
    return capsule[0]

def form_recipe_capsule_root(capsule):
    return capsule[1]

def form_recipe_capsule_surfaces(capsule):
    return capsule[2]

def form_recipe_capsule_capabilities(capsule):
    return capsule[3]

def form_recipe_capsule_contracts(capsule):
    return capsule[4]

def form_recipe_capsule_proofs(capsule):
    return capsule[5]

def form_recipe_capsule_costs(capsule):
    return capsule[6]

def form_recipe_capsule_specializers(capsule):
    return capsule[7]

def form_recipe_capsule_symbol_packs(capsule):
    return capsule[8]

def form_recipe_capsule_from_adapter(capsule, contracts, costs, specializers):
    return form_recipe_capsule(form_adapter_capsule_root(capsule), form_adapter_capsule_surfaces(capsule), form_adapter_capsule_capabilities(capsule), contracts, form_adapter_capsule_proofs(capsule), costs, specializers, form_adapter_capsule_symbol_packs(capsule))

def form_recipe_registry_node_from(capsules):
    return intern_node(FORM_RECIPE_REGISTRY, [intern_trivial_int(len(capsules))])

def form_recipe_registry(capsules):
    return [form_recipe_registry_node_from(capsules), capsules]

def form_recipe_registry_node(registry):
    return registry[0]

def form_recipe_registry_capsules(registry):
    return registry[1]

def form_recipe_registry_empty():
    return form_recipe_registry(empty())

def form_recipe_registry_add_capsule(registry, capsule):
    return form_recipe_registry(append(form_recipe_registry_capsules(registry), [capsule]))

def form_recipe_registry_merge(left, right):
    return form_recipe_registry(append(form_recipe_registry_capsules(left), form_recipe_registry_capsules(right)))

def form_recipe_capabilities_from_capsules(capsules):
    if is_nil(capsules):
        return empty()
    else:
        return append(form_recipe_capsule_capabilities(capsules[0]), form_recipe_capabilities_from_capsules(capsules[1:]))

def form_recipe_contracts_from_capsules(capsules):
    if is_nil(capsules):
        return empty()
    else:
        return append(form_recipe_capsule_contracts(capsules[0]), form_recipe_contracts_from_capsules(capsules[1:]))

def form_recipe_proofs_from_capsules(capsules):
    if is_nil(capsules):
        return empty()
    else:
        return append(form_recipe_capsule_proofs(capsules[0]), form_recipe_proofs_from_capsules(capsules[1:]))

def form_recipe_costs_from_capsules(capsules):
    if is_nil(capsules):
        return empty()
    else:
        return append(form_recipe_capsule_costs(capsules[0]), form_recipe_costs_from_capsules(capsules[1:]))

def form_recipe_specializers_from_capsules(capsules):
    if is_nil(capsules):
        return empty()
    else:
        return append(form_recipe_capsule_specializers(capsules[0]), form_recipe_specializers_from_capsules(capsules[1:]))

def form_recipe_registry_capabilities(registry):
    return form_recipe_capabilities_from_capsules(form_recipe_registry_capsules(registry))

def form_recipe_registry_contracts(registry):
    return form_recipe_contracts_from_capsules(form_recipe_registry_capsules(registry))

def form_recipe_registry_proofs(registry):
    return form_recipe_proofs_from_capsules(form_recipe_registry_capsules(registry))

def form_recipe_registry_costs(registry):
    return form_recipe_costs_from_capsules(form_recipe_registry_capsules(registry))

def form_recipe_registry_specializers(registry):
    return form_recipe_specializers_from_capsules(form_recipe_registry_capsules(registry))

def form_recipe_capability_by_node(capabilities, capability_node, missing):
    if is_nil(capabilities):
        return missing
    else:
        if node_eq(form_adapter_capability_node(capabilities[0]), capability_node):
            return capabilities[0]
        else:
            return form_recipe_capability_by_node(capabilities[1:], capability_node, missing)

def form_recipe_registry_capability_by_node(registry, capability_node, missing):
    return form_recipe_capability_by_node(form_recipe_registry_capabilities(registry), capability_node, missing)

def form_capability_contract_for(contracts, capability, missing):
    if is_nil(contracts):
        return missing
    else:
        if node_eq(form_capability_contract_capability_node(contracts[0]), form_adapter_capability_node(capability)):
            return contracts[0]
        else:
            return form_capability_contract_for(contracts[1:], capability, missing)

def form_capability_cost_for(costs, capability, missing):
    if is_nil(costs):
        return missing
    else:
        if node_eq(form_capability_cost_capability_node(costs[0]), form_adapter_capability_node(capability)):
            return costs[0]
        else:
            return form_capability_cost_for(costs[1:], capability, missing)

def form_capability_proof_for(proofs, capability, proof_kind, missing):
    if is_nil(proofs):
        return missing
    else:
        if (node_eq(form_adapter_capability_node(form_capability_proof_capability(proofs[0])), form_adapter_capability_node(capability)) and node_eq(form_capability_proof_kind(proofs[0]), proof_kind)):
            return proofs[0]
        else:
            return form_capability_proof_for(proofs[1:], capability, proof_kind, missing)

def form_capability_specializer_for(specializers, capability, specializer_kind, ctx, missing):
    if is_nil(specializers):
        return missing
    else:
        if (node_eq(form_adapter_capability_node(form_capability_specializer_capability(specializers[0])), form_adapter_capability_node(capability)) and (node_eq(form_capability_specializer_kind(specializers[0]), specializer_kind) and is_bmf_context_properties_match(ctx, form_capability_specializer_requirements(specializers[0])))):
            return specializers[0]
        else:
            return form_capability_specializer_for(specializers[1:], capability, specializer_kind, ctx, missing)

def is_form_capability_contract_satisfies(contract, effect, reversibility, lossiness, deterministic):
    return (node_eq(form_capability_contract_effect(contract), effect) and (node_eq(form_capability_contract_reversibility(contract), reversibility) and (node_eq(form_capability_contract_lossiness(contract), lossiness) and node_eq(form_capability_contract_deterministic(contract), deterministic))))

def form_recipe_capability_score(capability, contracts, costs, kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, missing):
    if is_form_adapter_capability_matches(capability, kind, input_surface, output_surface):
        contract = form_capability_contract_for(contracts, capability, missing)
        return ((0 - 1) if is_nil(contract) else (((cost := form_capability_cost_for(costs, capability, missing)), (bmf_context_properties_score(ctx, form_adapter_capability_requirements(capability)) + (0 if is_nil(cost) else form_capability_cost_score(cost))))[-1] if is_form_capability_contract_satisfies(contract, effect, reversibility, lossiness, deterministic) else (0 - 1)))
    else:
        return (0 - 1)

def form_recipe_find_capability_best(capabilities, contracts, costs, kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, best, best_score, missing):
    if is_nil(capabilities):
        return best
    else:
        score = form_recipe_capability_score(capabilities[0], contracts, costs, kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, missing)
        return (form_recipe_find_capability_best(capabilities[1:], contracts, costs, kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, capabilities[0], score, missing) if (score > best_score) else form_recipe_find_capability_best(capabilities[1:], contracts, costs, kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, best, best_score, missing))

def form_recipe_registry_find_capability(registry, kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, missing):
    return form_recipe_find_capability_best(form_recipe_registry_capabilities(registry), form_recipe_registry_contracts(registry), form_recipe_registry_costs(registry), kind, input_surface, output_surface, ctx, effect, reversibility, lossiness, deterministic, missing, (0 - 1), missing)

def form_recipe_registry_plan_flex(registry, input_surface, output_surface, ctx, depth, missing):
    return form_adapter_flex_plan_from_capabilities(form_recipe_registry_capabilities(registry), input_surface, output_surface, ctx, depth, missing)

def form_recipe_capability_run(capability, value, anchor, ctx):
    emit = form_adapter_capability_emit(capability)
    parse = form_adapter_capability_parse(capability)
    source = emit(value, anchor, ctx)
    return form_adapter_route(capability, source, parse(source, ctx))

def form_recipe_registry_run_capability(registry, capability_node, value, anchor, ctx, missing):
    capability = form_recipe_registry_capability_by_node(registry, capability_node, missing)
    return (missing if is_nil(capability) else form_recipe_capability_run(capability, value, anchor, ctx))

def form_recipe_registry_run_flex(registry, input_surface, output_surface, value, anchor, ctx, depth, missing):
    plan = form_recipe_registry_plan_flex(registry, input_surface, output_surface, ctx, depth, missing)
    return (missing if is_nil(plan) else form_adapter_plan_run(plan, value, anchor, ctx))

def form_adapter_capsule_node_from(root, surfaces, capabilities):
    return intern_node(FORM_ADAPTER_CAPSULE, [root, intern_trivial_int(len(surfaces)), intern_trivial_int(len(capabilities))])

def form_adapter_capsule(root, surfaces, capabilities, symbol_packs, proofs):
    return [form_adapter_capsule_node_from(root, surfaces, capabilities), root, surfaces, capabilities, symbol_packs, proofs]

def form_adapter_capsule_node(capsule):
    return capsule[0]

def form_adapter_capsule_root(capsule):
    return capsule[1]

def form_adapter_capsule_surfaces(capsule):
    return capsule[2]

def form_adapter_capsule_capabilities(capsule):
    return capsule[3]

def form_adapter_capsule_symbol_packs(capsule):
    return capsule[4]

def form_adapter_capsule_proofs(capsule):
    return capsule[5]

def form_adapter_registry_node_from(capsules):
    return intern_node(FORM_ADAPTER_REGISTRY, [intern_trivial_int(len(capsules))])

def form_adapter_registry(capsules):
    return [form_adapter_registry_node_from(capsules), capsules]

def form_adapter_registry_node(registry):
    return registry[0]

def form_adapter_registry_capsules(registry):
    return registry[1]

def form_adapter_capabilities_from_capsules(capsules):
    if is_nil(capsules):
        return empty()
    else:
        return append(form_adapter_capsule_capabilities(capsules[0]), form_adapter_capabilities_from_capsules(capsules[1:]))

def form_adapter_registry_capabilities(registry):
    return form_adapter_capabilities_from_capsules(form_adapter_registry_capsules(registry))

def is_form_adapter_capability_matches(capability, kind, input_surface, output_surface):
    return (node_eq(form_adapter_capability_kind(capability), kind) and (node_eq(form_adapter_capability_input_surface(capability), input_surface) and node_eq(form_adapter_capability_output_surface(capability), output_surface)))

def form_adapter_capability_score(capability, kind, input_surface, output_surface, ctx):
    if is_form_adapter_capability_matches(capability, kind, input_surface, output_surface):
        return bmf_context_properties_score(ctx, form_adapter_capability_requirements(capability))
    else:
        return (0 - 1)

def form_adapter_find_capability_best(capabilities, kind, input_surface, output_surface, ctx, best, best_score, missing):
    if is_nil(capabilities):
        return best
    else:
        score = form_adapter_capability_score(capabilities[0], kind, input_surface, output_surface, ctx)
        return (form_adapter_find_capability_best(capabilities[1:], kind, input_surface, output_surface, ctx, capabilities[0], score, missing) if (score > best_score) else form_adapter_find_capability_best(capabilities[1:], kind, input_surface, output_surface, ctx, best, best_score, missing))

def form_adapter_registry_find_capability(registry, kind, input_surface, output_surface, ctx, missing):
    return form_adapter_find_capability_best(form_adapter_registry_capabilities(registry), kind, input_surface, output_surface, ctx, missing, (0 - 1), missing)

def form_adapter_route_node_from(capability):
    return intern_node(FORM_ADAPTER_ROUTE, [form_adapter_capability_node(capability)])

def form_adapter_route(capability, source, parsed):
    return [form_adapter_route_node_from(capability), capability, source, parsed]

def form_adapter_route_node(route):
    return route[0]

def form_adapter_route_capability(route):
    return route[1]

def form_adapter_route_source(route):
    return route[2]

def form_adapter_route_parsed(route):
    return route[3]

def form_adapter_route_anchor(route):
    return form_adapter_route_parsed(route)[0]

def form_adapter_route_value(route):
    return form_adapter_route_parsed(route)[1]

def form_adapter_registry_roundtrip(registry, kind, input_surface, output_surface, value, anchor, ctx, missing):
    capability = form_adapter_registry_find_capability(registry, kind, input_surface, output_surface, ctx, missing)
    return (missing if is_nil(capability) else ((emit := form_adapter_capability_emit(capability)), (parse := form_adapter_capability_parse(capability)), (source := emit(value, anchor, ctx)), form_adapter_route(capability, source, parse(source, ctx)))[-1])

def is_form_adapter_capability_starts(capability, kind, input_surface, ctx):
    return (node_eq(form_adapter_capability_kind(capability), kind) and (node_eq(form_adapter_capability_input_surface(capability), input_surface) and is_bmf_context_properties_match(ctx, form_adapter_capability_requirements(capability))))

def is_form_adapter_capability_input_ready(capability, input_surface, ctx):
    return (node_eq(form_adapter_capability_input_surface(capability), input_surface) and is_bmf_context_properties_match(ctx, form_adapter_capability_requirements(capability)))

def form_adapter_plan_node_from(capabilities):
    return intern_node(FORM_ADAPTER_PLAN, [intern_trivial_int(len(capabilities))])

def form_adapter_plan(capabilities):
    return [form_adapter_plan_node_from(capabilities), capabilities]

def form_adapter_plan_node(plan):
    return plan[0]

def form_adapter_plan_capabilities(plan):
    return plan[1]

def is_form_adapter_plan_empty(plan):
    return is_nil(form_adapter_plan_capabilities(plan))

def form_adapter_plan_cons(capability, plan):
    return form_adapter_plan([capability, *form_adapter_plan_capabilities(plan)])

def form_adapter_plan_search(candidates, all_capabilities, kinds, input_surface, output_surface, ctx, missing):
    if is_nil(candidates):
        return missing
    else:
        capability = candidates[0]
        return (((rest_plan := form_adapter_plan_from_capabilities(all_capabilities, kinds[1:], form_adapter_capability_output_surface(capability), output_surface, ctx, missing)), (form_adapter_plan_search(candidates[1:], all_capabilities, kinds, input_surface, output_surface, ctx, missing) if is_nil(rest_plan) else form_adapter_plan_cons(capability, rest_plan)))[-1] if is_form_adapter_capability_starts(capability, kinds[0], input_surface, ctx) else form_adapter_plan_search(candidates[1:], all_capabilities, kinds, input_surface, output_surface, ctx, missing))

def form_adapter_plan_from_capabilities(capabilities, kinds, input_surface, output_surface, ctx, missing):
    if is_nil(kinds):
        if node_eq(input_surface, output_surface):
            return form_adapter_plan(empty())
        else:
            return missing
    else:
        return form_adapter_plan_search(capabilities, capabilities, kinds, input_surface, output_surface, ctx, missing)

def form_adapter_registry_plan(registry, kinds, input_surface, output_surface, ctx, missing):
    return form_adapter_plan_from_capabilities(form_adapter_registry_capabilities(registry), kinds, input_surface, output_surface, ctx, missing)

def form_adapter_flex_plan_search(candidates, all_capabilities, input_surface, output_surface, ctx, depth, missing):
    if is_nil(candidates):
        return missing
    else:
        capability = candidates[0]
        return (((rest_plan := form_adapter_flex_plan_from_capabilities(all_capabilities, form_adapter_capability_output_surface(capability), output_surface, ctx, (depth - 1), missing)), (form_adapter_flex_plan_search(candidates[1:], all_capabilities, input_surface, output_surface, ctx, depth, missing) if is_nil(rest_plan) else form_adapter_plan_cons(capability, rest_plan)))[-1] if is_form_adapter_capability_input_ready(capability, input_surface, ctx) else form_adapter_flex_plan_search(candidates[1:], all_capabilities, input_surface, output_surface, ctx, depth, missing))

def form_adapter_flex_plan_from_capabilities(capabilities, input_surface, output_surface, ctx, depth, missing):
    if node_eq(input_surface, output_surface):
        return form_adapter_plan(empty())
    else:
        if (depth < 1):
            return missing
        else:
            return form_adapter_flex_plan_search(capabilities, capabilities, input_surface, output_surface, ctx, depth, missing)

def form_adapter_registry_plan_flex(registry, input_surface, output_surface, ctx, depth, missing):
    return form_adapter_flex_plan_from_capabilities(form_adapter_registry_capabilities(registry), input_surface, output_surface, ctx, depth, missing)

def form_adapter_compiled_plan_node_from(plan):
    return intern_node(FORM_ADAPTER_COMPILED_PLAN, [form_adapter_plan_node(plan)])

def form_adapter_compiled_plan(plan):
    return [form_adapter_compiled_plan_node_from(plan), plan]

def form_adapter_compiled_plan_node(compiled):
    return compiled[0]

def form_adapter_compiled_plan_plan(compiled):
    return compiled[1]

def form_adapter_compiled_plan_capabilities(compiled):
    return form_adapter_plan_capabilities(form_adapter_compiled_plan_plan(compiled))

def form_adapter_registry_compile_flex(registry, input_surface, output_surface, ctx, depth, missing):
    plan = form_adapter_registry_plan_flex(registry, input_surface, output_surface, ctx, depth, missing)
    return (missing if is_nil(plan) else form_adapter_compiled_plan(plan))

def form_adapter_compiled_plan_run(compiled, value, anchor, ctx):
    return form_adapter_plan_run(form_adapter_compiled_plan_plan(compiled), value, anchor, ctx)

def form_adapter_plan_result_node_from(plan):
    return intern_node(FORM_ADAPTER_PLAN_RESULT, [form_adapter_plan_node(plan)])

def form_adapter_plan_result(plan, value, anchor, routes):
    return [form_adapter_plan_result_node_from(plan), plan, value, anchor, routes]

def form_adapter_plan_result_node(result):
    return result[0]

def form_adapter_plan_result_plan(result):
    return result[1]

def form_adapter_plan_result_value(result):
    return result[2]

def form_adapter_plan_result_anchor(result):
    return result[3]

def form_adapter_plan_result_routes(result):
    return result[4]

def form_adapter_plan_run_loop(capabilities, value, anchor, ctx, routes):
    if is_nil(capabilities):
        return [value, anchor, reverse(routes)]
    else:
        capability = capabilities[0]
        emit = form_adapter_capability_emit(capability)
        parse = form_adapter_capability_parse(capability)
        source = emit(value, anchor, ctx)
        parsed = parse(source, ctx)
        route = form_adapter_route(capability, source, parsed)
        return form_adapter_plan_run_loop(capabilities[1:], form_adapter_route_value(route), form_adapter_route_anchor(route), ctx, [route, *routes])

def form_adapter_plan_run(plan, value, anchor, ctx):
    output = form_adapter_plan_run_loop(form_adapter_plan_capabilities(plan), value, anchor, ctx, empty())
    return form_adapter_plan_result(plan, output[0], output[1], output[2])

def form_adapter_registry_plan_run(registry, kinds, input_surface, output_surface, value, anchor, ctx, missing):
    plan = form_adapter_registry_plan(registry, kinds, input_surface, output_surface, ctx, missing)
    return (missing if is_nil(plan) else form_adapter_plan_run(plan, value, anchor, ctx))

def is_bmf_context_property_matches(ctx, property):
    return str_eq(bmf_symbol_context_property(ctx, bmf_lens_property_key(property), ''), bmf_lens_property_value(property))

def is_bmf_context_properties_match(ctx, requirements):
    if is_nil(requirements):
        return True
    else:
        if is_bmf_context_property_matches(ctx, requirements[0]):
            return is_bmf_context_properties_match(ctx, requirements[1:])
        else:
            return False

def bmf_context_property_score(ctx, property):
    actual = bmf_symbol_context_property(ctx, bmf_lens_property_key(property), '')
    return (0 if str_eq(actual, '') else (1 if str_eq(actual, bmf_lens_property_value(property)) else (0 - 1)))

def bmf_context_properties_score_loop(ctx, requirements, score):
    if is_nil(requirements):
        return score
    else:
        item_score = bmf_context_property_score(ctx, requirements[0])
        return ((0 - 1) if (item_score < 0) else bmf_context_properties_score_loop(ctx, requirements[1:], (score + item_score)))

def bmf_context_properties_score(ctx, requirements):
    return bmf_context_properties_score_loop(ctx, requirements, 0)

def is_bmf_reverse_lens_context_matches(target, domain, lens, ctx):
    return (is_bmf_reverse_lens_matches(target, domain, lens) and is_bmf_context_properties_match(ctx, bmf_reverse_lens_requirements(target)))

def bmf_reverse_lens_context_score(target, domain, lens, ctx):
    if is_bmf_reverse_lens_matches(target, domain, lens):
        return bmf_context_properties_score(ctx, bmf_reverse_lens_requirements(target))
    else:
        return (0 - 1)

def bmf_reverse_lens_find_for_context(targets, domain, lens, ctx, missing):
    return bmf_reverse_lens_find_best_for_context(targets, domain, lens, ctx, missing, (0 - 1), missing)

def bmf_reverse_lens_find_best_for_context(targets, domain, lens, ctx, best, best_score, missing):
    if is_nil(targets):
        return best
    else:
        score = bmf_reverse_lens_context_score(targets[0], domain, lens, ctx)
        return (bmf_reverse_lens_find_best_for_context(targets[1:], domain, lens, ctx, targets[0], score, missing) if (score > best_score) else bmf_reverse_lens_find_best_for_context(targets[1:], domain, lens, ctx, best, best_score, missing))

def bmf_emit_through_lens(targets, domain, lens, node, anchor, ctx, missing):
    target = bmf_reverse_lens_find(targets, domain, lens, empty())
    return (missing if is_nil(target) else ((emit := bmf_reverse_lens_emit(target)), emit(node, anchor, ctx))[-1])

def bmf_parse_through_lens(targets, domain, lens, source, ctx, missing):
    target = bmf_reverse_lens_find(targets, domain, lens, empty())
    return (missing if is_nil(target) else ((parse := bmf_reverse_lens_parse(target)), parse(source, ctx))[-1])

def bmf_emit_through_context_lens(targets, domain, lens, node, anchor, ctx, missing):
    target = bmf_reverse_lens_find_for_context(targets, domain, lens, ctx, empty())
    return (missing if is_nil(target) else ((emit := bmf_reverse_lens_emit(target)), emit(node, anchor, ctx))[-1])

def bmf_parse_through_context_lens(targets, domain, lens, source, ctx, missing):
    target = bmf_reverse_lens_find_for_context(targets, domain, lens, ctx, empty())
    return (missing if is_nil(target) else ((parse := bmf_reverse_lens_parse(target)), parse(source, ctx))[-1])

def bmf_lens_roundtrip(targets, domain, lens, node, anchor, ctx, missing):
    source = bmf_emit_through_lens(targets, domain, lens, node, anchor, ctx, missing)
    parsed = bmf_parse_through_lens(targets, domain, lens, source, ctx, missing)
    return ['bmf-lens-roundtrip', source, parsed]

def bmf_lens_roundtrip_for_context(targets, domain, lens, node, anchor, ctx, missing):
    source = bmf_emit_through_context_lens(targets, domain, lens, node, anchor, ctx, missing)
    parsed = bmf_parse_through_context_lens(targets, domain, lens, source, ctx, missing)
    return ['bmf-lens-roundtrip', source, parsed]

def bmf_lens_roundtrip_source(rt):
    return rt[1]

def bmf_lens_roundtrip_parsed(rt):
    return rt[2]

def bmf_lens_roundtrip_anchor(rt):
    return bmf_lens_roundtrip_parsed(rt)[0]

def bmf_lens_roundtrip_node(rt):
    return bmf_lens_roundtrip_parsed(rt)[1]

def bmf_collection(objects):
    return ['bmf-collection', objects]

def is_bmf_collection(x):
    return ((len(x) > 0) and str_eq(x[0], 'bmf-collection'))

def bmf_collection_items(c):
    return c[1:][0]

def bmf_empty(_x):
    return bmf_collection(empty())

def bmf_identity_inverse(obj):
    return bmf_object_source(obj)

def bmf_reverse_object(obj):
    return cell_undo(obj)

def bmf_atom(kind, value):
    return bmf_object(kind, value, bmf_empty(0), bmf_identity_inverse)

def bmf_cap_to_object(cap):
    return bmf_object(cap_name(cap), cap_value(cap), bmf_empty(0), bmf_identity_inverse)

def bmf_caps_to_objects(caps):
    if is_nil(caps):
        return empty()
    else:
        return [bmf_cap_to_object(caps[0]), *bmf_caps_to_objects(caps[1:])]

def bmf_caps_to_collection(caps):
    return bmf_collection(bmf_caps_to_objects(caps))

def bmf_object_by_kind(objects, kind):
    if is_nil(objects):
        return empty()
    else:
        if str_eq(bmf_object_kind(objects[0]), kind):
            return objects[0]
        else:
            return bmf_object_by_kind(objects[1:], kind)

def bmf_collection_get(collection, kind):
    return bmf_object_by_kind(bmf_collection_items(collection), kind)

def bmf_collection_value(collection, kind):
    return bmf_object_value(bmf_collection_get(collection, kind))

def bmf_stack(items):
    return ['bmf-stack', items]

def bmf_stack_items(stack):
    return stack[1:][0]

def bmf_stack_push(stack, object):
    return bmf_stack([object, *bmf_stack_items(stack)])

def rev_step(acc, x):
    return [x, *acc]

def reverse_list(xs):
    return foldl(rev_step, empty(), xs)

def bmf_stack_reduce(stack):
    return bmf_collection(reverse_list(bmf_stack_items(stack)))

def bmf_frame(parent, stack):
    return ['bmf-frame', parent, stack]

def bmf_frame_parent(frame):
    return frame[1:][0]

def bmf_frame_stack(frame):
    return frame[1:][1:][0]

def bmf_start_result_stack(parent_stack):
    return bmf_frame(parent_stack, bmf_stack(empty()))

def bmf_frame_with_stack(frame, stack):
    return bmf_frame(bmf_frame_parent(frame), stack)

def bmf_end_result_stack(frame, tag, inverse):
    child_collection = bmf_stack_reduce(bmf_frame_stack(frame))
    grouped = bmf_object(tag, child_collection, child_collection, inverse)
    return bmf_stack_push(bmf_frame_parent(frame), grouped)

def rule_name(r):
    return r[0]

def rule_pattern(r):
    return r[1:][0]

def rule_action(r):
    return r[1:][1:][0]

def rule_inverse(r):
    if (len(r) > 3):
        return r[1:][1:][1:][0]
    else:
        return bmf_identity_inverse

def bmf_default_reverse_emitter(object):
    return bmf_object_source_span(object)

def rule_reverse_emitter(r):
    if (len(r) > 4):
        return r[4]
    else:
        return bmf_default_reverse_emitter

def bmf_native(name, action, category):
    return ['native', name, action, category]

def bmf_native_name(n):
    return n[1]

def bmf_native_action(n):
    return n[2]

def bmf_native_category(n):
    return n[3]

def form_section(dialect, object):
    return ['form-section', dialect, object]

def is_form_section(s):
    return ((len(s) > 0) and str_eq(s[0], 'form-section'))

def form_section_dialect(s):
    return s[1]

def form_section_object(s):
    return s[2]

def bmf_terminal(name):
    return ['bmf-terminal', name]

def bmf_capture(name, kind):
    return ['bmf-capture', name, kind]

def bmf_rule_spec(name, pattern, action):
    return ['bmf-rule-spec', name, pattern, action]

def bmf_reversible_rule_spec(name, pattern, action, reverse):
    return ['bmf-rule-spec', name, pattern, action, reverse]

def bmf_section(name, rules):
    return ['bmf-section', name, rules]

def bmf_section_name(s):
    return s[1]

def bmf_section_rules(s):
    return s[2]

def bml_word(value):
    return ['bml-word', value]

def bml_symbol(value):
    return ['bml-symbol', value]

def bml_section(items):
    return ['bml-section', items]

def is_bml_section(s):
    return ((len(s) > 0) and str_eq(s[0], 'bml-section'))

def bml_section_items(s):
    return s[1]

def bmf_dialect(name, rulebook, natives, rules):
    return ['bmf-dialect', name, rulebook, natives, rules]

def is_bmf_dialect(d):
    return ((len(d) > 0) and str_eq(d[0], 'bmf-dialect'))

def bmf_dialect_name(d):
    return d[1]

def bmf_dialect_rulebook(d):
    return d[2]

def bmf_dialect_natives(d):
    return d[3]

def bmf_dialect_rules(d):
    return d[4]

def bmf_dialect_rule_name(rule):
    return rule[0]

def bmf_dialect_find_rule_list(rules, rule_name):
    if is_nil(rules):
        return empty()
    else:
        if str_eq(bmf_dialect_rule_name(rules[0]), rule_name):
            return rules[0]
        else:
            return bmf_dialect_find_rule_list(rules[1:], rule_name)

def bmf_dialect_find_rule(dialect, rule_name):
    return bmf_dialect_find_rule_list(bmf_dialect_rules(dialect), rule_name)

def bmf_dialect_apply_rule(dialect, rule_name, object_stream):
    return apply_object_rule(bmf_dialect_find_rule(dialect, rule_name), object_stream)

def bmf_dialect_reverse_rule(dialect, rule_name, object):
    return apply_object_rule_reverse(bmf_dialect_find_rule(dialect, rule_name), object)

def bmf_runtime_grammar_request(anchor, dialect, rule_name, source):
    return ['bmf-runtime-grammar-request', anchor, dialect, rule_name, source]

def bmf_runtime_grammar_request_anchor(request):
    return request[1]

def bmf_runtime_grammar_request_dialect(request):
    return request[2]

def bmf_runtime_grammar_request_rule_name(request):
    return request[3]

def bmf_runtime_grammar_request_source(request):
    return request[4]

def bmf_runtime_grammar_object_request(anchor, dialect, rule_name, object):
    return ['bmf-runtime-grammar-object-request', anchor, dialect, rule_name, object]

def bmf_runtime_grammar_object_request_anchor(request):
    return request[1]

def bmf_runtime_grammar_object_request_dialect(request):
    return request[2]

def bmf_runtime_grammar_object_request_rule_name(request):
    return request[3]

def bmf_runtime_grammar_object_request_object(request):
    return request[4]

def bmf_runtime_grammar_emit_request(request, anchor, ctx):
    return request

def bmf_runtime_grammar_parse_request(request, ctx):
    match = bmf_dialect_apply_rule(bmf_runtime_grammar_request_dialect(request), bmf_runtime_grammar_request_rule_name(request), bmf_runtime_grammar_request_source(request))
    return [bmf_runtime_grammar_request_anchor(request), cap_get(match_caps(match), 'result')]

def bmf_runtime_grammar_emit_object_request(request, anchor, ctx):
    return request

def bmf_runtime_grammar_reverse_request(request, ctx):
    return [bmf_runtime_grammar_object_request_anchor(request), bmf_dialect_reverse_rule(bmf_runtime_grammar_object_request_dialect(request), bmf_runtime_grammar_object_request_rule_name(request), bmf_runtime_grammar_object_request_object(request))]

def bmf_runtime_dialect_capsule(root, dialect, source_surface, form_surface, parse_kind, emit_kind, effect, reversibility, lossiness, deterministic, proof_kind, proof_recipe, expected):
    parse_capability = form_adapter_capability(parse_kind, source_surface, form_surface, bmf_runtime_grammar_emit_request, bmf_runtime_grammar_parse_request, dialect, empty())
    emit_capability = form_adapter_capability(emit_kind, form_surface, source_surface, bmf_runtime_grammar_emit_object_request, bmf_runtime_grammar_reverse_request, dialect, empty())
    return form_recipe_capsule(root, [source_surface, form_surface], [parse_capability, emit_capability], [form_capability_contract(parse_capability, effect, reversibility, lossiness, deterministic, empty()), form_capability_contract(emit_capability, effect, reversibility, lossiness, deterministic, empty())], [form_capability_proof(parse_capability, proof_kind, proof_recipe, expected), form_capability_proof(emit_capability, proof_kind, proof_recipe, expected)], empty(), empty(), [dialect])

def object_lit(kind, value):
    return ['object', kind, value]

def object_pattern_tag(p):
    return p[0]

def match_object_pattern(p, object_stream):
    tag = object_pattern_tag(p)
    return (match_object_literal(p, object_stream) if str_eq(tag, 'object') else (match_object_sequence(p[1:], object_stream, cap_empty(0)) if str_eq(tag, 'sequence') else (match_object_choice(p[1:], object_stream) if str_eq(tag, 'choice') else (match_object_capture(p[1:][0], p[1:][1:][0], object_stream) if str_eq(tag, 'capture') else (match_object_star(p[1:][0], object_stream, empty()) if str_eq(tag, 'star') else (match_object_opt(p[1:][0], object_stream) if str_eq(tag, 'opt') else mk_fail(str_concat('unknown object pattern: ', tag))))))))

def match_object_literal(p, object_stream):
    if is_nil(object_stream):
        return mk_fail('expected BMF object')
    else:
        want_kind = p[1:][0]
        want_value = p[1:][1:][0]
        obj = object_stream[0]
        return ((mk_match(cap_empty(0), object_stream[1:]) if str_eq(want_value, '') else (mk_match(cap_empty(0), object_stream[1:]) if str_eq(bmf_object_value(obj), want_value) else mk_fail(str_concat('object value mismatch: expected ', want_value)))) if str_eq(bmf_object_kind(obj), want_kind) else mk_fail(str_concat('object kind mismatch: expected ', want_kind)))

def match_object_sequence(children, object_stream, acc_caps):
    if is_nil(children):
        return mk_match(acc_caps, object_stream)
    else:
        m = match_object_pattern(children[0], object_stream)
        return (m if is_fail(m) else match_object_sequence(children[1:], match_rest(m), cap_merge(acc_caps, match_caps(m))))

def match_object_choice(alternatives, object_stream):
    if is_nil(alternatives):
        return mk_fail('no object alternative matched')
    else:
        m = match_object_pattern(alternatives[0], object_stream)
        return (m if is_match(m) else match_object_choice(alternatives[1:], object_stream))

def capture_object_value(m, original_stream):
    if is_nil(match_caps(m)):
        return bmf_object_value(original_stream[0])
    else:
        return match_caps(m)

def match_object_capture(name, child, object_stream):
    m = match_object_pattern(child, object_stream)
    return (m if is_fail(m) else mk_match(cap_set(match_caps(m), name, capture_object_value(m, object_stream)), match_rest(m)))

def match_object_star(child, object_stream, collected):
    m = match_object_pattern(child, object_stream)
    return (mk_match(cap_set(cap_empty(0), 'items', collected), object_stream) if is_fail(m) else match_object_star(child, match_rest(m), [match_caps(m), *collected]))

def match_object_opt(child, object_stream):
    m = match_object_pattern(child, object_stream)
    return (mk_match(cap_empty(0), object_stream) if is_fail(m) else m)

def apply_object_rule(rule, object_stream):
    m = match_object_pattern(rule_pattern(rule), object_stream)
    return (m if is_fail(m) else ((captures := bmf_caps_to_collection(match_caps(m))), (source_span := take((len(object_stream) - len(match_rest(m))), object_stream)), (source := bmf_match_source(captures, source_span)), (action := rule_action(rule)), (recipe := action(captures)), (object := bmf_object(rule_name(rule), recipe, source, rule_inverse(rule))), mk_match(cap_set(cap_set(cap_empty(0), 'objects', captures), 'result', object), match_rest(m)))[-1])

def apply_object_rule_reverse(rule, object):
    emit = rule_reverse_emitter(rule)
    return emit(object)

def bmf_roundtrip(rule, source):
    first_match = apply_object_rule(rule, source)
    first_object = cap_get(match_caps(first_match), 'result')
    reverse_source = apply_object_rule_reverse(rule, first_object)
    second_match = apply_object_rule(rule, reverse_source)
    second_object = cap_get(match_caps(second_match), 'result')
    return ['bmf-roundtrip', first_object, reverse_source, second_object]

def bmf_roundtrip_first_object(rt):
    return rt[1]

def bmf_roundtrip_source(rt):
    return rt[2]

def bmf_roundtrip_second_object(rt):
    return rt[3]

def is_bmf_roundtrip_node_eq(rt):
    return node_eq(bmf_object_value(bmf_roundtrip_first_object(rt)), bmf_object_value(bmf_roundtrip_second_object(rt)))

if __name__ == '__main__':
    BMF_DOMAIN_REF = make_nodeid(8, 45, 4, 1)
    BMF_LENS_REF = make_nodeid(8, 45, 4, 2)
    BMF_DOMAIN_KIND_REF = make_nodeid(8, 45, 4, 3)
    BMF_SURFACE_REF = make_nodeid(8, 45, 4, 4)
    BMF_REVERSE_LENS = make_nodeid(8, 45, 3, 5)
    BMF_DOMAIN_CONTRACT = make_nodeid(8, 45, 3, 1)
    BMF_SURFACE_CONTRACT = make_nodeid(8, 45, 3, 2)
    BMF_LENS_CONTRACT = make_nodeid(8, 45, 3, 3)
    BMF_TRANSLATION_SPACE = make_nodeid(8, 45, 3, 4)
    FORM_CAPSULE_ROOT = make_nodeid(8, 45, 5, 1)
    FORM_DYNAMIC_KIND = make_nodeid(8, 45, 5, 2)
    FORM_DYNAMIC_REF = make_nodeid(8, 45, 5, 3)
    FORM_ADAPTER_CAPSULE = make_nodeid(8, 45, 5, 4)
    FORM_ADAPTER_CAPABILITY = make_nodeid(8, 45, 5, 5)
    FORM_ADAPTER_REGISTRY = make_nodeid(8, 45, 5, 6)
    FORM_ADAPTER_ROUTE = make_nodeid(8, 45, 5, 7)
    FORM_ADAPTER_PLAN = make_nodeid(8, 45, 5, 8)
    FORM_ADAPTER_PLAN_RESULT = make_nodeid(8, 45, 5, 9)
    FORM_ADAPTER_COMPILED_PLAN = make_nodeid(8, 45, 5, 10)
    FORM_CAPABILITY_CONTRACT = make_nodeid(8, 45, 5, 11)
    FORM_CAPABILITY_COST = make_nodeid(8, 45, 5, 12)
    FORM_CAPABILITY_PROOF = make_nodeid(8, 45, 5, 13)
    FORM_CAPABILITY_SPECIALIZER = make_nodeid(8, 45, 5, 14)
    FORM_RECIPE_CAPSULE = make_nodeid(8, 45, 5, 15)
    FORM_RECIPE_REGISTRY = make_nodeid(8, 45, 5, 16)
    print(0)
