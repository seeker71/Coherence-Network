# OSS Concept Mapping

How original Coherency Network concepts map to the Open Source Contribution Intelligence product.

| Original Concept | OSS Equivalent | Concrete Example |
|------------------|----------------|------------------|
| Concept (CC004) | Repository, package, or significant module | `npm/react`, `pypi/django`, `github/facebook/react` |
| Synergy Links (CC005) | Dependencies, imports, cross-project references | `react` → `prop-types`, `lodash`; `package.json` deps, `import` edges |
| Synergy Node (CC007) | Contributor (developer, maintainer, reviewer) | GitHub user `gaearon`, npm maintainer, PyPI uploader |
| Flow Events (CC003) | Commits, PRs, issues, releases, reviews | Commit SHA, PR #123, issue #45, npm publish v18.2.0 |
| Energy Token (CC001) | Attribution credits / funding units | GitHub Sponsors, Open Collective, grant allocation |
| Coherence Score | Project health (see algorithm) | 0.0–1.0 per project; composite of activity, diversity, docs |
| Harmony Agreements (CC002) | Contribution agreements, license terms | CLA, DCO, MIT/Apache-2.0, contributor covenant |
| Collective Wisdom (CC008) | Maintainer decisions, RFC processes | RFC merged, maintainer merge decision, TSC vote |
| Coherence Exchange (CC006) | Marketplace for funding, bounties, services | Bountysource, IssueHunt, custom bounty per issue |
| Concept Investment | Sponsoring / investing in projects or maintainers | Sponsor `@sindresorhus` on GitHub, fund `lodash` maintainer |

## Worked Example: npm/react

| Concept | Instance |
|---------|----------|
| Concept (CC004) | Package `react` at npm registry |
| Synergy Links | Depends on `loose-envify`, `object-assign`, `prop-types`; depended on by 100K+ packages |
| Synergy Nodes | Maintainers (e.g. `gaearon`, `acdlite`), contributors in commits |
| Flow Events | Commits to `facebook/react`, PRs, npm releases (e.g. 18.2.0) |
| Coherence Score | Composite of commit cadence, contributor count, dependency health, docs quality |
| Harmony Agreements | MIT license, React CLA for contributions |

## Coherence Rewards (COH003) — OSS Interpretation

- Incentivizes contributions that improve project health
- Metrics: contributor diversity, activity cadence, documentation, responsiveness
- Distribution: proportional to coherence impact and downstream dependency
- Feedback: maintainers see score, improvement suggestions, attribution

## Pitfalls to Avoid (from concept docs)

- Balance different contribution types (code, docs, triage)
- Prevent gaming (fake commits, artificial inflation)
- Balance short-term metrics vs long-term sustainability
