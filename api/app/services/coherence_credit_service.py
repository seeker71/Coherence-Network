"""Coherence Credit (CC) service — exchange rate loading and conversion functions.

Loads exchange rate config from data/exchange_rates.json with sensible defaults
if the file is missing. Caches config on first load (module-level singleton).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from app.models.coherence_credit import (
    CostVector,
    ExchangeRate,
    ExchangeRateConfig,
    ProviderRate,
    ValueVector,
)

# ---------------------------------------------------------------------------
# Default configuration (used when data/exchange_rates.json is missing)
# ---------------------------------------------------------------------------

_DEFAULT_PROVIDERS = [
    ProviderRate(
        provider_id="openrouter-sonnet",
        display_name="OpenRouter Claude Sonnet",
        cc_per_1k_input=1.0,
        cc_per_1k_output=4.0,
        cc_per_second=0.667,
        quality_score=0.85,
    ),
    ProviderRate(
        provider_id="openrouter-gpt4",
        display_name="OpenRouter GPT-4",
        cc_per_1k_input=10.0,
        cc_per_1k_output=30.0,
        cc_per_second=0.0,
        quality_score=0.82,
    ),
    ProviderRate(
        provider_id="local-llama",
        display_name="Local Llama",
        cc_per_1k_input=0.2,
        cc_per_1k_output=0.2,
        cc_per_second=0.1,
        quality_score=0.55,
    ),
]

_DEFAULT_RATE = ExchangeRate(
    epoch="2026-Q1",
    cc_per_usd=333.33,
    reference_model="claude-sonnet-4-20250514",
    reference_rate_usd=0.003,
    human_hour_cc=500.0,
    notes="Default rate. 1 CC = $0.003 (1K tokens on reference model).",
)

_DEFAULT_CONFIG = ExchangeRateConfig(
    current_epoch="2026-Q1",
    rates=[_DEFAULT_RATE],
    providers=_DEFAULT_PROVIDERS,
)

# ---------------------------------------------------------------------------
# Config loading (cached singleton)
# ---------------------------------------------------------------------------

_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
    "exchange_rates.json",
)

_cached_config: Optional[ExchangeRateConfig] = None


def _load_config() -> ExchangeRateConfig:
    """Load exchange rate config from JSON file, falling back to defaults."""
    try:
        path = Path(_CONFIG_FILE)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            # Strip non-model fields like "description"
            filtered = {k: v for k, v in raw.items() if k in ExchangeRateConfig.model_fields}
            return ExchangeRateConfig(**filtered)
    except Exception:
        pass
    return _DEFAULT_CONFIG


def _get_config() -> ExchangeRateConfig:
    global _cached_config
    if _cached_config is None:
        _cached_config = _load_config()
    return _cached_config


def reset_config() -> None:
    """Reset cached config (useful for testing)."""
    global _cached_config
    _cached_config = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def current_rate(epoch: Optional[str] = None) -> ExchangeRate:
    """Return the active ExchangeRate, or the rate for a specific epoch."""
    config = _get_config()
    target_epoch = epoch or config.current_epoch
    for rate in config.rates:
        if rate.epoch == target_epoch:
            return rate
    # Fallback: return first rate or default
    if config.rates:
        return config.rates[0]
    return _DEFAULT_RATE


def cc_from_usd(amount_usd: float, epoch: Optional[str] = None) -> float:
    """Convert USD to Coherence Credits using the active (or specified) epoch rate."""
    rate = current_rate(epoch)
    return amount_usd * rate.cc_per_usd


def usd_from_cc(amount_cc: float, epoch: Optional[str] = None) -> float:
    """Convert Coherence Credits to USD using the active (or specified) epoch rate."""
    rate = current_rate(epoch)
    return amount_cc / rate.cc_per_usd


def provider_rate(provider_id: str) -> Optional[ProviderRate]:
    """Return ProviderRate for a given provider_id, or None if not found."""
    config = _get_config()
    for p in config.providers:
        if p.provider_id == provider_id:
            return p
    return None


def compute_cost_vector(
    compute_cc: float = 0.0,
    infrastructure_cc: float = 0.0,
    human_attention_cc: float = 0.0,
    opportunity_cc: float = 0.0,
    external_cc: float = 0.0,
) -> CostVector:
    """Build a CostVector with auto-summed total_cc."""
    total = compute_cc + infrastructure_cc + human_attention_cc + opportunity_cc + external_cc
    return CostVector(
        total_cc=total,
        compute_cc=compute_cc,
        infrastructure_cc=infrastructure_cc,
        human_attention_cc=human_attention_cc,
        opportunity_cc=opportunity_cc,
        external_cc=external_cc,
    )


def compute_value_vector(
    adoption_cc: float = 0.0,
    lineage_cc: float = 0.0,
    friction_avoided_cc: float = 0.0,
    revenue_cc: float = 0.0,
) -> ValueVector:
    """Build a ValueVector with auto-summed total_cc."""
    total = adoption_cc + lineage_cc + friction_avoided_cc + revenue_cc
    return ValueVector(
        total_cc=total,
        adoption_cc=adoption_cc,
        lineage_cc=lineage_cc,
        friction_avoided_cc=friction_avoided_cc,
        revenue_cc=revenue_cc,
    )
