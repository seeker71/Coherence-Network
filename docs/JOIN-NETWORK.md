# Join the Coherence Network

Run this on any machine to become a contributing node.

## Setup

```bash
git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network/api
pip install -e .
```

## Run

```bash
python scripts/local_runner.py --timeout 300
```

That's it. The runner auto-detects your providers (claude, codex, gemini, cursor, ollama), registers with the hub, picks tasks, executes them, and pushes measurements.

## Verify

```bash
curl https://api.coherencycoin.com/api/federation/nodes
```

Your machine should appear with its hostname, OS, and detected providers.

## What it does

- Picks highest-ROI tasks from the idea portfolio
- Routes to the best provider for each task type (data-driven, not hardcoded)
- File tasks (spec/impl/test) go to tool-capable providers only
- Review tasks go to any provider
- Outcomes feed Thompson Sampling — the network learns what works
- Measurements visible at https://coherencycoin.com/automation

## Optional: continuous mode

```bash
python scripts/local_runner.py --timeout 300 --loop --interval 120
```
