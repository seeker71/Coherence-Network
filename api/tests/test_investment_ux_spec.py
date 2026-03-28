"""Contract tests for Investment UX (`investment-ux`).

No separate markdown spec is checked in under that slug; acceptance criteria are derived from
the public `/invest` surface (`web/app/invest/page.tsx`, `web/app/invest/InvestBalanceSection.tsx`)
and the backing read APIs they call.

Acceptance criteria verified here:

- **R1 — Public invest route**: page module exists, metadata identifies the Invest surface, and
  primary navigation exposes `/invest` for discoverability.
- **R2 — Data contract**: the server component loads the idea portfolio from
  `GET /api/ideas?limit=60` (same-origin API base via `getApiBase()`).
- **R3 — Ranking & signals**: ideas are sorted by ROI proxy (`value_gap` / `estimated_cost`);
  each card surfaces title, manifestation stage, value gap, estimated cost, and ROI affordance.
- **R4 — Stake CTA**: each row links to `/ideas/{id}` and exposes a visible Stake action.
- **R5 — Balance context**: the client balance strip reads `GET /api/contributions/ledger/{id}`
  after persisting contributor id under `coherence_contributor_id` in `localStorage`.
- **R6 — Empty & resilience**: empty portfolio shows invite copy and a path back to share ideas;
  fetch failures yield an empty list (no throw in `loadIdeas`).
- **R7 — Wayfinding**: footer nav links to ideas, contribute, and resonance.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INVEST_PAGE = _REPO_ROOT / "web" / "app" / "invest" / "page.tsx"
_BALANCE_SECTION = _REPO_ROOT / "web" / "app" / "invest" / "InvestBalanceSection.tsx"
_SITE_HEADER = _REPO_ROOT / "web" / "components" / "site_header.tsx"

client = TestClient(app)


def _invest_src() -> str:
    assert _INVEST_PAGE.is_file(), f"Missing {_INVEST_PAGE}"
    return _INVEST_PAGE.read_text(encoding="utf-8")


def _balance_src() -> str:
    assert _BALANCE_SECTION.is_file(), f"Missing {_BALANCE_SECTION}"
    return _BALANCE_SECTION.read_text(encoding="utf-8")


# --- API contracts (always-on with TestClient) ---


def test_api_ideas_list_supports_invest_page_limit() -> None:
    """Invest page requests `limit=60`; API must accept and return 200 + ideas envelope."""
    response = client.get("/api/ideas?limit=60")
    assert response.status_code == 200
    data = response.json()
    assert "ideas" in data
    assert isinstance(data["ideas"], list)


def test_api_contributions_ledger_path_exists_for_balance_section() -> None:
    """Balance section calls ledger by contributor id; service returns balance envelope."""
    response = client.get("/api/contributions/ledger/nonexistent-test-contributor-ux")
    assert response.status_code == 200
    data = response.json()
    assert "balance" in data


# --- Invest page (static contract) ---


def test_invest_page_loads_portfolio_from_documented_endpoint() -> None:
    """R2: server fetch targets `/api/ideas` with limit=60."""
    src = _invest_src()
    assert "/api/ideas?limit=60" in src
    assert 'cache: "no-store"' in src


def test_invest_page_metadata_title_and_revalidate() -> None:
    """R1: page exports Invest metadata and short ISR window."""
    src = _invest_src()
    assert 'title: "Invest"' in src
    assert "export const revalidate = 90" in src


def test_invest_page_sorts_by_roi_and_computes_display() -> None:
    """R3: ROI ordering and bar cap match implementation."""
    src = _invest_src()
    assert "computeRoi" in src
    assert "value_gap" in src and "estimated_cost" in src
    assert "roiBarWidth" in src
    assert "(roi / 20) * 100" in src or "roi / 20" in src


def test_invest_page_cards_surface_required_fields() -> None:
    """R3–R4: cards show gap, est. cost, ROI, stage, and idea deep links."""
    src = _invest_src()
    assert "Value gap" in src
    assert "Est. cost" in src
    assert "ROI" in src
    assert "humanizeManifestationStatus" in src
    assert "manifestation_status" in src
    assert "Stake" in src
    assert 'href={`/ideas/${encodeURIComponent(idea.id)}`}' in src


def test_invest_page_empty_state_and_resilient_load() -> None:
    """R6: graceful empty list + try/catch returning []."""
    src = _invest_src()
    assert "No ideas yet" in src
    assert "Share an idea" in src
    assert "try {" in src and "return []" in src


def test_invest_page_wayfinding_links() -> None:
    """R7: secondary navigation strip."""
    src = _invest_src()
    assert 'href="/ideas"' in src
    assert 'href="/contribute"' in src
    assert 'href="/resonance"' in src
    assert 'aria-label="Where to go next"' in src


def test_invest_page_imports_balance_section() -> None:
    """Balance strip is part of the invest UX."""
    src = _invest_src()
    assert "InvestBalanceSection" in src


# --- Balance section (static contract) ---


def test_balance_section_ledger_endpoint_and_storage_key() -> None:
    """R5: ledger URL pattern and localStorage key."""
    src = _balance_src()
    assert "coherence_contributor_id" in src
    assert "/api/contributions/ledger/" in src
    assert "encodeURIComponent" in src


def test_balance_section_labels_and_actions() -> None:
    """R5: user-visible balance chrome."""
    src = _balance_src()
    assert "Your CC Balance" in src
    assert "Contributor:" in src
    assert "Save" in src
    assert "change" in src


def test_balance_section_handles_failed_ledger_fetch() -> None:
    """R5: non-OK response clears balance without throwing."""
    src = _balance_src()
    assert "setBalance(null)" in src
    assert "if (!res.ok)" in src


# --- Global nav discoverability ---


def test_site_header_links_invest_route() -> None:
    """R1: `/invest` is linked from secondary navigation."""
    assert _SITE_HEADER.is_file()
    text = _SITE_HEADER.read_text(encoding="utf-8")
    assert '/invest' in text
    assert "Invest" in text


def test_invest_page_stake_helper_copy_pattern() -> None:
    """Stake description ties CC to task estimate (regression guard)."""
    src = _invest_src()
    assert "stakeDescription" in src
    assert "10 CC" in src


def test_invest_page_sorted_copy_matches_roi_comparator() -> None:
    """Sorted ideas use computeRoi descending (best opportunities first)."""
    src = _invest_src()
    assert "computeRoi(b) - computeRoi(a)" in src
