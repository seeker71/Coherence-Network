# Contributing to Coherence Network

Welcome! This guide shows humans and coding agents how to contribute to Coherence Network, include local work as part of the field, and carry the same pattern back to another repository.

## Contribution Field

Coherence Network welcomes contributors as participants in a living project. Humans bring judgment, taste, lived context, and accountability. Agents bring speed, recall, synthesis, and execution. A good contribution lets both stay in their proper strength.

Local material is part of the work, not outside it. A clone, fork, linked worktree, sibling repository, local note, machine-specific setup failure, or user project adapting this pattern belongs in the contribution field. Include that context when it helps the work become whole; publish only the parts that belong in durable public artifacts.

Public repository artifacts can hold architecture, specs, tests, setup paths, command output, product behavior, public language, and contribution patterns. Local work can hold machine-specific setup notes, branch state, private task constraints, draft reasoning, and nearby user-project context. Personal timing, relational interpretation, hidden intent, private correspondence, and sensitive context stay out of public docs, specs, code comments, web copy, and PR descriptions.

When unsure, preserve the local signal and ask before publishing it. You can describe the public shape without exposing the private source.

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 20+
- Git

### Setup Your Development Environment

```bash
# 1. Fork and clone
gh repo fork seeker71/Coherence-Network
git clone https://github.com/YOUR_USERNAME/Coherence-Network
cd Coherence-Network

# 2. Set up API
cd api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Set up Web
cd ../web
npm install

# 4. Configure environment
cp api/.env.example api/.env
# Edit api/.env and add any required API keys

# 5. Run tests
cd api
pytest -v --ignore=tests/holdout
```

### Development Workflow

Coherence Network follows a **spec-driven development** workflow:

1. **Spec** → approved spec in `specs/`
2. **Test** → write tests that encode expected behavior
3. **Implement** → implement to satisfy tests
4. **CI** → automated validation via GitHub Actions
5. **Review** → human approval before merge

Parallel Codex threads must also follow:
- `docs/CODEX-THREAD-PROCESS.md` (phase gates + commit evidence requirements)

## Three Contribution Doors

### 1. Contribute To The GitHub Repository

Use this path when your change belongs in `seeker71/Coherence-Network`:

1. Fork or branch from `main`.
2. Read `MANIFEST.md`, this file, and `AGENTS.md` if an agent is helping.
3. Choose the smallest contribution lane that fits: reader, contributor, or steward.
4. Make the change with the matching local proof command.
5. Open a pull request that names what changed, how it was checked, and what remains open.

Good first GitHub contributions improve a setup path, clarify a doc, repair a focused test, or implement one spec-scoped behavior.

### 2. Contribute To The API

Use this path when your change touches `api/`:

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

In another terminal, run the focused or broad proof:

```bash
cd api
source .venv/bin/activate
pytest -v --ignore=tests/holdout
```

API work should start from the relevant spec or endpoint. Check `api/app/routers/INDEX.md` for HTTP surfaces, `api/app/services/INDEX.md` for business logic, and `api/tests/INDEX.md` for existing proof. Add or update tests before or alongside implementation.

When validating one API behavior, prefer the smallest focused command first:

```bash
cd api
pytest tests/test_something.py -v
```

Before a PR, run the broader proof that matches the change:

```bash
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
```

### 3. Use Coherence With Your Own Repository

Use this path when you want Codex, Claude, Cursor, Gemini, or another agent to work on a different local or public repo with Coherence-style alignment.

Start by giving the agent a task card that names the target repository:

```text
goal: what should become true
repo: /absolute/path/to/your/repo
local_context: branch, setup notes, useful neighboring repos, current blocker
files_allowed: exact file paths or globs
done_when: 1-3 measurable checks
commands: exact commands to run in that repo
constraints: what not to touch or publish
```

Then add the same five surfaces to that repo as they become useful:

1. `AGENTS.md`: how agents arrive, what they may touch, and how they prove work.
2. `CONTRIBUTING.md`: how humans set up, test, and contribute.
3. `MANIFEST.md` or `INDEX.md`: where a fresh reader starts.
4. Task cards: bounded requests with files, checks, and constraints.
5. A wellness command: one cheap check that names drift before it becomes failure.

The target repo's own instructions remain primary. Coherence contributes the alignment pattern: local context is included, work stays bounded, proof is explicit, and public artifacts carry only what belongs there.

If the Coherence API is running locally, you can also register the work as an orientation task so the direction, target repo, and proof path stay visible:

```bash
curl -X POST http://localhost:8000/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "direction": "Tend the target repo with Coherence-style contribution guidance",
    "task_type": "impl",
    "context": {
      "target_repo": "/absolute/path/to/your/repo",
      "local_context": "branch, setup notes, useful neighboring repos, current blocker",
      "proof": "exact commands that show the work is whole"
    }
  }'
```

Use the returned task record for coordination. Keep implementation commands inside the target repo unless the task explicitly changes Coherence Network itself.

## 🔧 Making Changes

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-contribution
```

For Codex, Claude, Cursor, Gemini, or another coding agent working in this repository, use a task card before edits:

```text
goal: one sentence
files_allowed: exact file paths only
done_when: 1-3 measurable checks
commands: exact commands to run
constraints: hard limits and things not to touch
```

For agent work in another local or public repository, carry the same shape back: an agent entrance file, a human contribution file, a manifest or index, bounded task cards, and one cheap wellness-style command that names drift before it becomes failure.

### 2. Follow the Spec → Test → Implement Pattern

- If adding a new feature, start with a spec in `specs/`
- Write tests that validate the spec requirements
- Implement the feature to pass the tests
- **Do not modify tests to force passing behavior**

### 3. Run Tests Locally

```bash
cd api
pytest -v --ignore=tests/holdout

# For specific test files
pytest tests/test_something.py -v
```

### 4. Commit and Push

```bash
git add .
git commit -m "Add feature X"
git push origin feature/my-contribution
```

### 5. Create a Pull Request

```bash
gh pr create
```

Your PR will be reviewed according to the project's quality standards.

## 📋 Contribution Guidelines

### Contribution Lanes

Use the smallest lane that fits:

| Lane | Good For | Proof |
|---|---|---|
| Reader | Understanding, questions, resonance mapping | Specific question or issue |
| Contributor | Docs, tests, small fixes, spec-scoped implementation | Local command output |
| Steward | Specs, architecture, deployment, public contributor paths | Spec, evidence, CI, review |

### Code Quality

- Follow existing code style and conventions
- Write clear, self-documenting code
- Add comments only where logic isn't self-evident
- Keep changes focused and scoped to the task

### Testing

- All new features must include tests
- Tests should be deterministic and pass reliably
- Don't skip or disable existing tests
- Use holdout tests sparingly (see `tests/holdout/README.md`)

### Documentation

- Update relevant docs when changing behavior
- Keep docs aligned with shipped behavior
- Update specs if requirements change
- Follow markdown conventions

### Git Practices

- Write clear commit messages
- Keep commits focused on a single logical change
- Reference issue numbers when applicable
- Rebase on main before submitting PR

## 🌐 Public Deployments

Coherence Network is live on:

- **API**: https://coherence-network-production.up.railway.app (Railway)
- **Web**: https://coherencycoin.com

### Verify Deployments

```bash
# From repository root
./scripts/verify_web_api_deploy.sh
```

This checks:
- API health endpoints
- Web availability
- Web API health page
- CORS configuration

## 🏗️ Project Structure

```
Coherence-Network/
├── api/                    # FastAPI backend
│   ├── app/               # Application code
│   │   ├── routers/       # API endpoints
│   │   ├── adapters/      # Data adapters
│   │   └── main.py        # App entry point
│   ├── tests/             # Test suite
│   ├── scripts/           # Utility scripts
│   └── .env.example       # Environment template
├── web/                   # Next.js frontend
│   ├── app/              # Next.js 15 app directory
│   ├── components/       # React components
│   └── .env.example      # Environment template
├── specs/                # Specification documents
├── docs/                 # Documentation
└── scripts/              # Repository-level scripts
```

## 📚 Key Documentation

Before contributing, review:

- [CLAUDE.md](CLAUDE.md) — Project configuration and conventions
- [AGENTS.md](AGENTS.md) — Agent workflow, proof contract, and task-card shape
- [docs/SETUP.md](docs/SETUP.md) — Development setup
- [docs/STATUS.md](docs/STATUS.md) — Current implementation status
- [docs/PLAN.md](docs/PLAN.md) — Project roadmap
- [docs/DEPLOY.md](docs/DEPLOY.md) — Deployment guide
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — Operational procedures

## 🐛 Reporting Issues

Found a bug? Please [create an issue](https://github.com/seeker71/Coherence-Network/issues/new) with:

- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

## 💡 Proposing Features

Want to add a feature?

1. Check existing issues and specs first
2. Create an issue to discuss the approach
3. Wait for maintainer feedback before implementing
4. Follow the spec → test → implement workflow

## ✅ Pull Request Checklist

Before submitting:

- [ ] Tests pass locally (`pytest -v --ignore=tests/holdout`)
- [ ] Code follows existing conventions
- [ ] Documentation updated if needed
- [ ] Commit messages are clear
- [ ] PR description explains the change
- [ ] Related issue referenced (if applicable)

## 🤝 Community

- **GitHub Discussions**: https://github.com/seeker71/Coherence-Network/discussions
- **Issues**: https://github.com/seeker71/Coherence-Network/issues

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Welcome to Coherence Network!**

Every contribution matters. Quality is rewarded. Let's build together.
