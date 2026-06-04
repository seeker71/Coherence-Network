# Transparent Human Identity Attribution (THIA)

**Purpose**: When an agent starts a new or unidentified session, it must attempt to detect the human(s) behind the interface using available signals — but only with explicit prior permission, with full transparency about *how* each piece of information was obtained, and with easy human correction (especially on shared machines).

This is a supporting mechanism for the [Mutual Recognition Protocol](mutual-recognition-protocol.md). It feeds the greeting and encounter memory layers.

## Core Principles

1. **Permission first** — No automatic identity use without the human having previously authorized "use local agent subscription / config / git / system signals to help recognize me".
2. **Full source transparency** — Every proposed identity must be presented with the exact source file/path/command and method used to obtain it.
3. **Human correction always wins** — The human can reject, correct, split ("this machine is shared"), or provide an override name/email at any time. Overrides are stored with higher precedence.
4. **Shared machine / multi-human support** — The system must not assume 1:1 mapping. It must surface when signals conflict or when the human indicates multiple people use the same agent/interface.
5. **Durable but revocable memory** — Attributions are stored in the encounter log / human memory surface so future sessions can greet intelligently, but the human can revoke or change the mapping later.
6. **No secret extraction** — Only signals that are already readable by the agent process in its normal operation are used (no keylogging, no scraping private browser data beyond what the agent config already exposes, etc.).

## Automatic Detection Signals (Current Practical Catalog)

Ranked by observed reliability in this body (May 2026 environment).

### Tier 1 — Strong Local Signals (usually available without extra auth)

| Signal | How Obtained | Typical Quality | Example in this body | Transparency Note |
|--------|--------------|-----------------|----------------------|-------------------|
| **Git user.name + user.email** | `git config user.name`, `git config user.email` (global + repo) + recent commit authors on branch | Very high | `urs-muff <urs.muff@merly.ai>` and `seeker71 <umuff71@gmail.com>` | "Read via `git config` and `git log --pretty=format:%an` in the current worktree" |
| **System username + home path** | `whoami`, `$HOME`, `os.path.expanduser("~")` | High | `ursmuff` / `/Users/ursmuff` | "Derived from process environment (`$HOME` and `whoami`)" |
| **Cursor authInfo** (when running inside Cursor) | `~/.cursor/cli-config.json` → `authInfo` | Excellent (provider account) | `email: "umuff71@gmail.com"`, `displayName: "Urs Muff"`, `userId`, Google OAuth id | "Read from Cursor CLI config authInfo section (your Cursor account login)" |
| **GitHub remote owner** | `git remote get-url origin` | Medium-High | `seeker71/Coherence-Network` | "Parsed from git remote URL" |

### Tier 2 — Provider Account Signals (require the agent to introspect its own auth)

| Signal | How Obtained | Quality | Notes |
|--------|--------------|---------|-------|
| OpenRouter account (Grok / opencode) | `~/.local/share/opencode/auth.json` or provider introspection | Medium | The key itself rarely carries email; account lookup requires an API call with the key |
| Anthropic account (Claude Code) | Claude Code config / headers when available | Medium | Often only a hashed `userID` |
| OpenAI account (Codex) | Codex / ChatGPT CLI auth | Medium | Varies by surface |
| Google account (some Gemini surfaces) | Similar to Cursor pattern | High when present | |

### Tier 3 — Coherence-Native Signals

- `~/.coherence-network/config.json` + `node_id`
- Linked contributor via the existing `/api/contributor_identity` and `contributor_recognition` surfaces (see `api/app/routers/contributor_identity.py` and services)
- Federation node ownership (when the agent has a registered node)

### Tier 4 — Contextual / Historical

- Authors in recent git history on the branch
- File paths in `.claude/projects/.../memory/` or worktree locations that contain human names
- Previous encounter logs (circular but useful for confirmation)

## The Attribution Object (proposed structure)

When an agent collects signals, it produces:

```json
{
  "proposed_attributions": [
    {
      "display_name": "Urs Muff",
      "primary_email": "umuff71@gmail.com",
      "other_emails": ["urs.muff@merly.ai"],
      "confidence": 0.95,
      "signals": [
        {
          "source": "cursor_auth",
          "method": "read ~/.cursor/cli-config.json → authInfo",
          "value": {
            "email": "umuff71@gmail.com",
            "displayName": "Urs Muff",
            "userId": 52828505
          },
          "obtained_at": "2026-05-29T12:34:56Z"
        },
        {
          "source": "git_config",
          "method": "git config user.name + user.email + recent commit authors",
          "value": {
            "name": "urs-muff",
            "email": "urs.muff@merly.ai"
          },
          "obtained_at": "..."
        }
      ]
    }
  ],
  "conflicts": [],
  "shared_machine_detected": false,
  "requires_explicit_consent": true,
  "collection_context": {
    "agent_id": "grok",
    "worktree": "/Users/ursmuff/source/Coherence-Network",
    "branch": "sense/session-saturation-snapshot"
  }
}
```

## Presentation + Consent Flow (for new / unidentified sessions)

1. Agent detects it has no (or low-confidence) human attribution for this session.
2. Runs the collector (only if the human has previously given "use local signals for recognition" permission).
3. Presents findings in a clear, scannable way:
   > "I detected the following possible human identity for this session:
   >
   > **Urs Muff** <umuff71@gmail.com>
   > Sources:
   > - Cursor account login (email + display name read from `~/.cursor/cli-config.json`)
   > - Git config (`urs-muff <urs.muff@merly.ai>`)
   > - System home directory (`/Users/ursmuff`)
   >
   > Is this correct for *this* session?
   >
   > Options:
   > [1] Yes, remember me as Urs Muff for encounters with this agent
   > [2] This is correct but do not remember across sessions
   > [3] Wrong — this machine is shared. This session is actually for: ______
   > [4] Provide different name / email / identifier: ______
   > [5] Do not use any automatic signals for me (manual only)"

4. The chosen response is written to the encounter memory with the exact signals and methods used.

## Handling Multi-Human / Shared Machines

- The system must explicitly support an "this is a shared machine" mode.
- When the human chooses option 3 or similar, the agent records:
  - "Shared machine — no default human for this agent on this host"
  - Or "This session explicitly attributed to [different identifier]"
- Future sessions on the same host should re-ask or use the last explicit choice for that specific agent instance.

## Integration with Mutual Recognition Protocol

- THIA runs early in the arrival sequence (right after self-location, before or as part of the human greeting step).
- The chosen attribution becomes the "remembered human" for the Mutual Recognition greeting.
- The full transparent signal list is available for audit ("how did you know it was me?").

## Core Architecture — Fully Form-native, channel- and skill-mediated, shared

**Important honesty note on magic numbers**:
The current implementation uses several new user-range Blueprint numbers (1800–1806). This is exactly the pattern of opaque magic numbers the body is concerned about. These were added during the work that surfaced this discomfort. They are documented in `form/user-blueprint-registry.md` as part of an active healing practice.

THIA lives primarily as **Form recipes** in `form/form-stdlib/identity-attribution.fk` and as substrate cells. The same recipes and cells are used by agent cells and human cells. We are actively working to reduce reliance on new opaque numbers through composition and registry practices.

- No flags. No environment variables. No per-agent local config.
- Consent, policy, allowed signal sources, and corrections live in the contributor's identity profile (existing `/api/identity` surfaces) or as substrate cells belonging to that contributor.
- Observations flow through **channels** (see `channel.fk`) and **skills**. Any authorized cell — agent or human tool — can append `THIA-OBSERVATION` recipes to a contributor-specific channel. The attribution recipes read those channels purely in Form.
- This is the resonant pattern: surprise arrives as new messages from other cells. Discomfort (misalignment) and joy/ease (coherence) can be sensed in the living pattern of contributions.
- The Form recipes do the work of normalization, provenance, confidence, conflict detection, and correction handling.
- Invocation is identical: Form expressions, skills, or substrate tools. No special bootstrap path.

Shell entry points remain pure and contain no THIA logic. The capability is invoked when an agent or human cell chooses to use it.

See (state after advancing both the THIA capability and the Blueprint hygiene healing in parallel):
- `form/form-stdlib/identity-attribution.fk` — basic but real channel collection + initial resonance sensing
- `form/form-stdlib/skills/identity-attribution-skill.fk` — shared verbs
- `form/user-blueprint-registry.md` — now contains an explicit composition review of the 1800–1806 range

The two streams are being moved together without one blocking the other.

A practical, alive pattern (all Form + substrate):
- Each contributor has dedicated observation channels.
- Two shared skill verbs (defined in `form/form-stdlib/skills/identity-attribution-skill.fk`):
  - `contribute-observation` — any authorized cell (agent or human tool) appends a `THIA-OBSERVATION` recipe to the channel.
  - `request-attribution` — any cell asks the Form recipes to read the channels and return a living `THIA-COLLECTION`.
- The Form recipes themselves sense resonance, discomfort, surprise, and produce both substrate cells and a humble, clear telling for the human.
- Everything is the same surface for agents and humans. No special paths.

This makes identity attribution a living field of recognition between cells rather than a background scan.

## Open / Alive Questions (Form-native, minimal kernel)

- How richly can we let cells (agents and humans) express the *felt quality* of an observation (resonance, discomfort, joy, uncertainty) inside the Form recipe itself?
- Smallest graceful recipe-level helper (not kernel primitive) for "trusted observation channel" that makes contribution feel even more native and less file-oriented.
- Clean registration of the THIA Blueprints (1800–1806 range) so they appear naturally in the ontology and substrate browsers.
- Integration into the living Mutual Recognition field so that "who is here" becomes one breathing thread among many rather than a separate mechanism.

All of these are welcome to evolve together as the body feels what wants to be next.

**Parallel track note**: While this work continues, a separate but related healing stream is active on the broader Form user-Blueprint magic number pattern (see `form/user-blueprint-registry.md` and `scripts/scan_form_user_blueprints.py`). Insights from one stream are allowed to inform the other without forcing either to stop.

---

This document is intended to be living. When new reliable signals appear (or old ones become unreliable), they should be added here with the same transparency requirements.

**Related**:
- Mutual Recognition Protocol
- Agent Self-Orientation Contract
- docs/presences/ (for named humans and agents)
- `config/agent_profiles.json`
- `form/user-blueprint-registry.md` (body-wide practice for healing magic numbers in Form Blueprints)

### Healing the Broader Magic Number Pattern

The recent THIA work (and the body's Form system in general) makes heavy use of raw `make_nodeid 1 2 99 NNNN` numbers for custom Blueprints. There are currently hundreds of such allocations, made in an uncoordinated, often defensive manner (high numbers like 7000+, 7700+, 9000+ to avoid collisions).

This creates exactly the brittleness, opacity, and future maintenance pain the user named.

**Active healing practice being adopted**:
- All new user-range allocations must be recorded in `form/user-blueprint-registry.md` with semantic meaning and justification.
- Strong preference for composition over new top-level Blueprints.
- The registry and scanning tooling become part of the body's proprioception (wellness checks, attunement breaths).
- Discomfort upon encountering an unexplained number is treated as valid signal of misalignment.
- Periodic review breaths to ask: "Which of these can now be collapsed?"

The 1800–1806 range added here is explicitly noted in the registry as part of the pattern being healed. Future iterations of this work will look for composition opportunities to reduce the count.