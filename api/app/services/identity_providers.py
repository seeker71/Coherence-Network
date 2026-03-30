"""Identity provider registry — single source of truth for all supported providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    key: str
    label: str
    placeholder: str
    category: str
    can_oauth: bool = False
    can_verify: bool = False


# ---------------------------------------------------------------------------
# Registry — grouped by 6 categories (Social, Dev, Crypto/Web3, Professional, Identity, Platform)
# Total: 37 providers
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY: dict[str, list[ProviderInfo]] = {
    "Social": [
        ProviderInfo("x", "X (Twitter)", "@handle", "Social"),
        ProviderInfo("discord", "Discord", "username#0000 or user ID", "Social"),
        ProviderInfo("telegram", "Telegram", "@username", "Social"),
        ProviderInfo("reddit", "Reddit", "u/username", "Social"),
        ProviderInfo("mastodon", "Mastodon", "user@instance.social", "Social"),
        ProviderInfo("bluesky", "Bluesky", "handle.bsky.social", "Social"),
        ProviderInfo("youtube", "YouTube", "channel ID or @handle", "Social"),
    ],
    "Dev": [
        ProviderInfo("github", "GitHub", "username", "Dev", can_oauth=True),
        ProviderInfo("gitlab", "GitLab", "username", "Dev"),
        ProviderInfo("bitbucket", "Bitbucket", "username", "Dev"),
        ProviderInfo("npm", "npm", "npm username", "Dev"),
        ProviderInfo("pypi", "PyPI", "PyPI username", "Dev"),
        ProviderInfo("crates", "crates.io", "crates.io username", "Dev"),
        ProviderInfo("stackoverflow", "Stack Overflow", "user ID", "Dev"),
    ],
    "Crypto / Web3": [
        ProviderInfo("ethereum", "Ethereum", "0x address", "Crypto / Web3", can_verify=True),
        ProviderInfo("bitcoin", "Bitcoin", "BTC address", "Crypto / Web3"),
        ProviderInfo("solana", "Solana", "SOL address", "Crypto / Web3"),
        ProviderInfo("cosmos", "Cosmos", "cosmos1... address", "Crypto / Web3"),
        ProviderInfo("nostr", "Nostr", "npub or hex pubkey", "Crypto / Web3"),
        ProviderInfo("ens", "ENS", "name.eth", "Crypto / Web3"),
        ProviderInfo("lens", "Lens Protocol", "handle.lens", "Crypto / Web3"),
    ],
    "Professional": [
        ProviderInfo("linkedin", "LinkedIn", "profile slug or URL", "Professional"),
        ProviderInfo("email", "Email", "you@example.com", "Professional"),
        ProviderInfo("google", "Google", "Google email", "Professional", can_oauth=True),
        ProviderInfo("apple", "Apple", "Apple ID email", "Professional"),
        ProviderInfo("microsoft", "Microsoft", "Microsoft email", "Professional"),
        ProviderInfo("orcid", "ORCID", "0000-0000-0000-0000", "Professional"),
    ],
    "Identity": [
        ProviderInfo("did", "DID (W3C)", "did:method:identifier", "Identity"),
        ProviderInfo("keybase", "Keybase", "username", "Identity"),
        ProviderInfo("pgp", "PGP", "key fingerprint", "Identity"),
        ProviderInfo("okta", "Okta", "Okta ID", "Identity"),
        ProviderInfo("auth0", "Auth0", "Auth0 ID", "Identity"),
    ],
    "Platform": [
        ProviderInfo("slack", "Slack", "workspace:username", "Platform"),
        ProviderInfo("zoom", "Zoom", "Zoom email", "Platform"),
        ProviderInfo("notion", "Notion", "Notion username or ID", "Platform"),
        ProviderInfo("trello", "Trello", "Trello username", "Platform"),
        ProviderInfo("asana", "Asana", "Asana email", "Platform"),
    ],
}

# Flat list of all provider keys
SUPPORTED_PROVIDERS: list[str] = [
    p.key for providers in PROVIDER_REGISTRY.values() for p in providers
]


def get_provider_info(key: str) -> ProviderInfo | None:
    """Look up provider metadata by key."""
    for providers in PROVIDER_REGISTRY.values():
        for p in providers:
            if p.key == key:
                return p
    return None


def get_categories() -> list[str]:
    """Return ordered list of category names."""
    return list(PROVIDER_REGISTRY.keys())


def registry_as_dict() -> dict:
    """Return the full registry as a JSON-serializable dict."""
    return {
        category: [
            {
                "key": p.key,
                "label": p.label,
                "placeholder": p.placeholder,
                "category": p.category,
                "canOAuth": p.can_oauth,
                "canVerify": p.can_verify,
            }
            for p in providers
        ]
        for category, providers in PROVIDER_REGISTRY.items()
    }
