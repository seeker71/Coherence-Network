"""Coherence-substrate — content-addressed numeric lattice for the Network.

A structural substrate for the body's tissue (ideas, specs, concepts,
memories, presences, lineages, tasks, witnesses). The kernel is universal;
the category vocabulary is Network-specific.

Public API:
    from app.services.substrate import (
        NodeID, Recipe, NamedCell,
        make_cell, lookup_cell, find_equivalent_cells,
        intern_node, lattice_stats,
        ingest_memory_file,
    )

See:
    docs/field/urs/artifacts/nums-go-2023/network-substrate-design.md
    docs/field/urs/artifacts/nums-go-2023/study-notes.md
"""
from __future__ import annotations

from app.services.substrate.kernel import (
    DOMAIN_BLUEPRINT,
    DOMAIN_RECIPE,
    CellView,
    NamedCell,
    NodeID,
    PathAnnotation,
    Recipe,
    annotate_path,
    find_cells_compatible_with,
    find_equivalent_cells,
    get_level,
    intern_node,
    lattice_stats,
    lookup_cell,
    lookup_node,
    make_cell,
    make_composite_blueprint,
    make_trivial_blueprint,
    serialize_tree,
    view_cell_through_blueprint,
)
from app.services.substrate.form import (
    FormResult,
    evaluate as form_evaluate,
    evaluate_text as form_evaluate_text,
    parse as form_parse,
    serialize_cell as form_serialize_cell,
    serialize_node_id as form_serialize_node_id,
)
from app.services.substrate.grammar import (
    BID_grammar,
    FormRule,
    list_form_rules,
    lookup_form_rule,
    register_form_rule,
)
from app.services.substrate.form_builders import (
    Build,
    CaptureRef,
    Const,
    execute_template,
    make_builder_from_template,
    recipe_to_template,
    template_to_recipe,
)
from app.services.substrate.self_host import (
    bootstrap_self_host,
    list_bootstrap_self_host_keywords,
)
from app.services.substrate.form_rules import (
    Capture,
    IdentCapture,
    Literal,
    Opt,
    RepeatedCapture,
    Sequence,
    list_builders,
    list_registered_keywords,
    load_all_keywords_from_substrate,
    load_keyword_from_substrate,
    lookup_builder,
    lookup_form_keyword,
    pattern_to_recipe,
    recipe_to_pattern,
    register_builder,
    register_form_keyword,
    unregister_form_keyword,
)
from app.services.substrate.markdown_frontend import (
    BID_concept,
    BID_idea,
    BID_memory,
    BID_object,
    BID_path,
    BID_presence,
    BID_slug,
    BID_spec,
    BID_string,
    frontmatter_to_blueprint,
    ingest_concept_file,
    ingest_idea_file,
    ingest_memory_file,
    ingest_presence_file,
    ingest_spec_file,
    parse_markdown,
    parse_markdown_file,
)

__all__ = [
    # kernel
    "CellView",
    "DOMAIN_BLUEPRINT",
    "DOMAIN_RECIPE",
    "NamedCell",
    "NodeID",
    "PathAnnotation",
    "Recipe",
    "annotate_path",
    "find_cells_compatible_with",
    "find_equivalent_cells",
    "get_level",
    "intern_node",
    "lattice_stats",
    "lookup_cell",
    "lookup_node",
    "make_cell",
    "make_composite_blueprint",
    "make_trivial_blueprint",
    "serialize_tree",
    "view_cell_through_blueprint",
    # category constructors
    "BID_concept",
    "BID_idea",
    "BID_memory",
    "BID_object",
    "BID_path",
    "BID_presence",
    "BID_slug",
    "BID_spec",
    "BID_string",
    # frontends
    "frontmatter_to_blueprint",
    "ingest_concept_file",
    "ingest_idea_file",
    "ingest_memory_file",
    "ingest_presence_file",
    "ingest_spec_file",
    "parse_markdown",
    "parse_markdown_file",
    # Form
    "FormResult",
    "form_evaluate",
    "form_evaluate_text",
    "form_parse",
    "form_serialize_cell",
    "form_serialize_node_id",
    # Grammar — substrate-resident parse rules (BMF-shaped seed)
    "BID_grammar",
    "FormRule",
    "list_form_rules",
    "lookup_form_rule",
    "register_form_rule",
    # Rule-driven extension — runtime keyword registration
    "Capture",
    "IdentCapture",
    "Literal",
    "Opt",
    "RepeatedCapture",
    "Sequence",
    "list_builders",
    "list_registered_keywords",
    "load_all_keywords_from_substrate",
    "load_keyword_from_substrate",
    "lookup_builder",
    "lookup_form_keyword",
    "pattern_to_recipe",
    "recipe_to_pattern",
    "register_builder",
    "register_form_keyword",
    "unregister_form_keyword",
    # Substrate-resident builders (Build/CaptureRef/Const template DSL)
    "Build",
    "CaptureRef",
    "Const",
    "execute_template",
    "make_builder_from_template",
    "recipe_to_template",
    "template_to_recipe",
    # Self-hosting (partial — re-expresses if / unless / whenever)
    "bootstrap_self_host",
    "list_bootstrap_self_host_keywords",
]
