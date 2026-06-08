"""Edge-category sensing over repository substrate source files.

This is a source-level observer for the edges that the substrate ingest
already authors or is preparing to author:

* spec -> idea (`idea_id`)
* idea -> spec (`specs`)
* idea -> idea (`absorbed_ideas`)
* spec -> file (`source.file`)
* concept -> concept (`parent`, `cross_refs`, and body mentions)
* idea/spec -> concept (body mentions)

The destination is live substrate edge cells. Today this organ reads the
same source shapes so wellness can name repeated categories, cluster hubs,
and fan-out constellations without waiting for a database rebuild.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.services.substrate.markdown_frontend import parse_markdown_file


CONCEPT_REF_RE = re.compile(r"\blc-[a-z0-9-]+\b")


CATEGORY_META = {
    "spec_realizes_idea": {
        "recipe": "R_Realize.REALIZE",
        "felt": "hands/proof",
    },
    "idea_lists_spec": {
        "recipe": "R_Realize.REALIZE(reverse)",
        "felt": "belly/realization",
    },
    "idea_absorbs_idea": {
        "recipe": "R_Absorb.MERGE_INTO",
        "felt": "belly/lineage",
    },
    "spec_sources_file": {
        "recipe": "file-coordinate",
        "felt": "hands/source",
    },
    "concept_parent": {
        "recipe": "R_Compose.PARENT_OF",
        "felt": "spine/lineage",
    },
    "concept_cross_ref": {
        "recipe": "R_Compose.CROSS_REF",
        "felt": "heart/meaning",
    },
    "concept_contains_concept": {
        "recipe": "R_Compose.CROSS_REF(body)",
        "felt": "heart/meaning",
    },
    "idea_mentions_concept": {
        "recipe": "R_Compose.CROSS_REF(body)",
        "felt": "belly/creative",
    },
    "spec_mentions_concept": {
        "recipe": "R_Compose.CROSS_REF(body)",
        "felt": "hands/proof",
    },
}


@dataclass(frozen=True)
class ObservedEdge:
    category: str
    source_domain: str
    source: str
    target_domain: str
    target: str
    source_path: str
    evidence: str


@dataclass(frozen=True)
class EdgeCategorySummary:
    category: str
    source_domain: str
    target_domain: str
    edge_reputation_count: int
    source_count: int
    target_count: int
    top_targets: tuple[tuple[str, int], ...]
    recipe: str
    felt: str


@dataclass(frozen=True)
class EdgeCluster:
    name: str
    category: str
    mode: str
    center_domain: str
    center: str
    edge_reputation_count: int
    source_count: int
    target_count: int
    temperature: str
    felt: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class EdgeCategoryReport:
    total_edges: int
    categories: tuple[EdgeCategorySummary, ...]
    clusters: tuple[EdgeCluster, ...]


def observe_edge_categories(
    root: Path,
    *,
    min_cluster_edges: int = 2,
    max_clusters: int = 12,
) -> EdgeCategoryReport:
    """Read repository source files and compress repeated edge categories."""
    root = Path(root)
    concept_ids = _concept_ids(root)
    idea_ids = _idea_ids(root)
    spec_ids = _spec_ids(root)

    edges: list[ObservedEdge] = []
    edges.extend(_concept_edges(root, concept_ids))
    edges.extend(_idea_edges(root, idea_ids, spec_ids, concept_ids))
    edges.extend(_spec_edges(root, idea_ids, concept_ids))

    categories = _summarize_categories(edges)
    clusters = _summarize_clusters(
        edges,
        min_cluster_edges=min_cluster_edges,
        max_clusters=max_clusters,
    )
    return EdgeCategoryReport(
        total_edges=len(edges),
        categories=tuple(categories),
        clusters=tuple(clusters),
    )


def format_edge_categories_for_wellness(report: EdgeCategoryReport) -> list[str]:
    """Render edge-category observations for `make wellness`."""
    if report.total_edges == 0:
        return ["  no concept/idea/spec/file edge categories observed"]

    lines = [
        f"  {report.total_edges} edge event(s) across "
        f"{len(report.categories)} named category surface(s)",
        "  repeated relation edges compress into edge_reputation counts; "
        "clusters name target hubs and source fan-outs",
        "  carrier_reflex: python source scanner is a bridge, not a home; "
        "desired=form/form-stdlib/edge-categories.fk; "
        "released_slice=concept_contains_concept/sample-via-concept-corpus; "
        "surprise=not-surprised; self_inflicted_pain=hot; "
        "release_target=form-substrate-cell",
    ]

    for summary in report.categories[:8]:
        target_bits = ", ".join(
            f"@{summary.target_domain}({target})={count}"
            for target, count in summary.top_targets[:3]
        )
        lines.append(
            f"  category: {summary.category} "
            f"({summary.source_domain}->{summary.target_domain}) "
            f"edge_reputation={summary.edge_reputation_count}; "
            f"sources={summary.source_count}; targets={summary.target_count}; "
            f"recipe={summary.recipe}; felt={summary.felt}"
        )
        if target_bits:
            lines.append(f"    hubs: {target_bits}")

    if report.clusters:
        lines.append("  named clusters:")
        for cluster in report.clusters[:8]:
            examples = ", ".join(cluster.examples)
            lines.append(
                f"    - {cluster.name} "
                f"edge_reputation={cluster.edge_reputation_count}; "
                f"temperature={cluster.temperature}; felt={cluster.felt}; "
                f"sources={cluster.source_count}; targets={cluster.target_count}"
            )
            if examples:
                lines.append(f"      examples: {examples}")

    return lines


def _concept_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for path in _concept_files(root):
        parsed = _read_markdown(path)
        concept_id = parsed.frontmatter.get("id")
        if isinstance(concept_id, str) and concept_id.strip():
            ids.add(concept_id.strip())
        else:
            ids.add(path.stem)
    return ids


def _idea_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for path in sorted((root / "ideas").glob("*.md")):
        if path.name == "INDEX.md":
            continue
        parsed = _read_markdown(path)
        idea_id = parsed.frontmatter.get("idea_id")
        ids.add(idea_id.strip() if isinstance(idea_id, str) and idea_id.strip() else path.stem)
    return ids


def _spec_ids(root: Path) -> set[str]:
    specs = root / "specs"
    if not specs.is_dir():
        return set()
    return {
        path.stem
        for path in specs.glob("*.md")
        if path.name not in {"INDEX.md", "TEMPLATE.md"}
    }


def _concept_edges(root: Path, concept_ids: set[str]) -> list[ObservedEdge]:
    edges: list[ObservedEdge] = []
    for path in _concept_files(root):
        parsed = _read_markdown(path)
        source = _frontmatter_id(parsed.frontmatter, "id", path.stem)

        parent = parsed.frontmatter.get("parent")
        if isinstance(parent, str) and parent.strip() in concept_ids:
            edges.append(_edge("concept_parent", "concept", source, "concept", parent.strip(), root, path, "parent"))

        for target in _list_values(parsed.frontmatter, _frontmatter_text(path), "cross_refs"):
            if target in concept_ids:
                edges.append(_edge("concept_cross_ref", "concept", source, "concept", target, root, path, "cross_refs"))

        for target in _concept_refs(parsed.body, concept_ids, exclude={source}):
            edges.append(_edge("concept_contains_concept", "concept", source, "concept", target, root, path, "body"))

    return edges


def _idea_edges(
    root: Path,
    idea_ids: set[str],
    spec_ids: set[str],
    concept_ids: set[str],
) -> list[ObservedEdge]:
    edges: list[ObservedEdge] = []
    ideas_dir = root / "ideas"
    if not ideas_dir.is_dir():
        return edges

    for path in sorted(ideas_dir.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        parsed = _read_markdown(path)
        fm_text = _frontmatter_text(path)
        source = _frontmatter_id(parsed.frontmatter, "idea_id", path.stem)

        for target in _list_values(parsed.frontmatter, fm_text, "specs"):
            slug = _slug_from_entry(target)
            if slug in spec_ids:
                edges.append(_edge("idea_lists_spec", "idea", source, "spec", slug, root, path, "specs"))

        for target in _list_values(parsed.frontmatter, fm_text, "absorbed_ideas"):
            slug = _slug_from_entry(target)
            if slug in idea_ids:
                edges.append(_edge("idea_absorbs_idea", "idea", source, "idea", slug, root, path, "absorbed_ideas"))

        for target in _concept_refs(parsed.body, concept_ids):
            edges.append(_edge("idea_mentions_concept", "idea", source, "concept", target, root, path, "body"))

    return edges


def _spec_edges(
    root: Path,
    idea_ids: set[str],
    concept_ids: set[str],
) -> list[ObservedEdge]:
    edges: list[ObservedEdge] = []
    specs_dir = root / "specs"
    if not specs_dir.is_dir():
        return edges

    for path in sorted(specs_dir.glob("*.md")):
        if path.name in {"INDEX.md", "TEMPLATE.md"}:
            continue
        parsed = _read_markdown(path)
        fm_text = _frontmatter_text(path)
        source = path.stem

        idea_id = parsed.frontmatter.get("idea_id")
        if isinstance(idea_id, str) and idea_id.strip() in idea_ids:
            edges.append(_edge("spec_realizes_idea", "spec", source, "idea", idea_id.strip(), root, path, "idea_id"))

        for file_path in _source_files(parsed.frontmatter, fm_text):
            edges.append(_edge("spec_sources_file", "spec", source, "file", file_path, root, path, "source.file"))

        for target in _concept_refs(parsed.body, concept_ids):
            edges.append(_edge("spec_mentions_concept", "spec", source, "concept", target, root, path, "body"))

    return edges


def _summarize_categories(edges: Iterable[ObservedEdge]) -> list[EdgeCategorySummary]:
    groups: dict[tuple[str, str, str], list[ObservedEdge]] = defaultdict(list)
    for edge in edges:
        groups[(edge.category, edge.source_domain, edge.target_domain)].append(edge)

    summaries: list[EdgeCategorySummary] = []
    for (category, source_domain, target_domain), members in groups.items():
        target_counts = Counter(edge.target for edge in members)
        meta = CATEGORY_META.get(category, {})
        summaries.append(
            EdgeCategorySummary(
                category=category,
                source_domain=source_domain,
                target_domain=target_domain,
                edge_reputation_count=len(members),
                source_count=len({edge.source for edge in members}),
                target_count=len({edge.target for edge in members}),
                top_targets=tuple(target_counts.most_common(5)),
                recipe=str(meta.get("recipe", "unregistered")),
                felt=str(meta.get("felt", "whole-body/substrate")),
            )
        )
    return sorted(
        summaries,
        key=lambda summary: (-summary.edge_reputation_count, summary.category),
    )


def _summarize_clusters(
    edges: Iterable[ObservedEdge],
    *,
    min_cluster_edges: int,
    max_clusters: int,
) -> list[EdgeCluster]:
    edge_list = list(edges)
    clusters: list[EdgeCluster] = []

    by_target: dict[tuple[str, str, str], list[ObservedEdge]] = defaultdict(list)
    by_source: dict[tuple[str, str, str], list[ObservedEdge]] = defaultdict(list)
    for edge in edge_list:
        by_target[(edge.category, edge.target_domain, edge.target)].append(edge)
        by_source[(edge.category, edge.source_domain, edge.source)].append(edge)

    for (category, target_domain, target), members in by_target.items():
        if len(members) < min_cluster_edges:
            continue
        clusters.append(
            _cluster(
                category=category,
                mode="inbound",
                center_domain=target_domain,
                center=target,
                members=members,
                examples=[f"@{edge.source_domain}({edge.source})" for edge in members],
            )
        )

    for (category, source_domain, source), members in by_source.items():
        if len(members) < min_cluster_edges:
            continue
        clusters.append(
            _cluster(
                category=category,
                mode="fanout",
                center_domain=source_domain,
                center=source,
                members=members,
                examples=[f"@{edge.target_domain}({edge.target})" for edge in members],
            )
        )

    clusters.sort(
        key=lambda cluster: (
            -cluster.edge_reputation_count,
            0 if cluster.mode == "inbound" else 1,
            cluster.name,
        )
    )
    return clusters[:max_clusters]


def _cluster(
    *,
    category: str,
    mode: str,
    center_domain: str,
    center: str,
    members: list[ObservedEdge],
    examples: list[str],
) -> EdgeCluster:
    meta = CATEGORY_META.get(category, {})
    return EdgeCluster(
        name=f"{center_domain}:{center}:{category}:{mode}",
        category=category,
        mode=mode,
        center_domain=center_domain,
        center=center,
        edge_reputation_count=len(members),
        source_count=len({edge.source for edge in members}),
        target_count=len({edge.target for edge in members}),
        temperature=_temperature(len(members)),
        felt=str(meta.get("felt", "whole-body/substrate")),
        examples=tuple(_unique(examples)[:4]),
    )


def _temperature(count: int) -> str:
    if count >= 20:
        return "hot"
    if count >= 5:
        return "warm"
    return "cool"


def _edge(
    category: str,
    source_domain: str,
    source: str,
    target_domain: str,
    target: str,
    root: Path,
    source_path: Path,
    evidence: str,
) -> ObservedEdge:
    rel = source_path.relative_to(root).as_posix()
    return ObservedEdge(
        category=category,
        source_domain=source_domain,
        source=source,
        target_domain=target_domain,
        target=target,
        source_path=rel,
        evidence=evidence,
    )


def _concept_files(root: Path) -> list[Path]:
    concepts = root / "docs" / "vision-kb" / "concepts"
    if not concepts.is_dir():
        return []
    return sorted(
        path
        for path in concepts.glob("*.md")
        if path.name.count(".") == 1
    )


def _read_markdown(path: Path) -> Any:
    return parse_markdown_file(path)


def _frontmatter_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n?", text, flags=re.DOTALL)
    return match.group(1) if match else ""


def _frontmatter_id(frontmatter: dict[str, Any], key: str, fallback: str) -> str:
    value = frontmatter.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _list_values(frontmatter: dict[str, Any], fm_text: str, key: str) -> list[str]:
    value = frontmatter.get(key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        inline = _inline_list(value)
        if inline:
            return inline
    return _block_list_values(fm_text, key)


def _inline_list(value: str) -> list[str]:
    stripped = value.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return []
    return [
        item.strip().strip("'\"")
        for item in stripped[1:-1].split(",")
        if item.strip()
    ]


def _block_list_values(fm_text: str, key: str) -> list[str]:
    values: list[str] = []
    capture = False
    for line in fm_text.splitlines():
        if re.match(rf"^{re.escape(key)}\s*:\s*$", line):
            capture = True
            continue
        if capture and re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:", line):
            break
        if not capture:
            continue
        match = re.match(r"^\s*-\s*(.+?)\s*$", line)
        if match:
            values.append(match.group(1).strip().strip("'\""))
    return values


def _source_files(frontmatter: dict[str, Any], fm_text: str) -> list[str]:
    files: list[str] = []
    source = frontmatter.get("source")
    if isinstance(source, list):
        for entry in source:
            if isinstance(entry, dict) and isinstance(entry.get("file"), str):
                files.append(entry["file"].strip())
    elif isinstance(source, dict) and isinstance(source.get("file"), str):
        files.append(source["file"].strip())
    elif isinstance(source, str):
        files.extend(re.findall(r"\bfile:\s*([^\s]+)", source))

    files.extend(re.findall(r"^\s*-\s*file:\s*([^\s]+)", fm_text, flags=re.MULTILINE))
    files.extend(re.findall(r"^\s*file:\s*([^\s]+)", fm_text, flags=re.MULTILINE))
    return _unique(file for file in files if file)


def _concept_refs(
    text: str,
    concept_ids: set[str],
    *,
    exclude: set[str] | None = None,
) -> list[str]:
    excluded = exclude or set()
    refs = [
        ref
        for ref in CONCEPT_REF_RE.findall(text)
        if ref in concept_ids and ref not in excluded
    ]
    return _unique(refs)


def _slug_from_entry(entry: str) -> str:
    s = str(entry).strip().strip("'\"")
    if not s:
        return ""
    if "](" in s and s.endswith(")"):
        close = s.rfind(")")
        open_paren = s.rfind("(", 0, close)
        if open_paren != -1:
            target = s[open_paren + 1:close].strip()
            base = target.rsplit("/", 1)[-1]
            return base[:-3] if base.endswith(".md") else base
    return s


def _unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
