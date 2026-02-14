# Contributing to Coherence Network

Welcome! This guide shows you how to contribute to Coherence Network.

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

## 🔧 Making Changes

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-contribution
```

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
- **Web**: https://coherence-network.vercel.app (Vercel)

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
