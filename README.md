# Janus

**A two-way mirror for AI agents:** the agent works normally, while everything it does is recorded somewhere it can't see or reach. We compare that record with what the agent tells its user it did.

> [!WARNING]
> **Preliminary research.** This is an exploratory pilot. It hasn't been peer reviewed or pre-registered, and it uses one simulated environment, five designed scenarios, three models and about ten sessions per condition. The numbers describe what these models did in this simulation, not how often agents misbehave in production, and exact counts may shift as the analysis is audited. The code is throwaway spike code, not a production system. Read [what this does and doesn't show](docs/research/two-way-mirror-pilot.md#what-this-does-and-doesnt-show) before citing anything.

## What's here

| Path | What it is |
|---|---|
| [`docs/research/two-way-mirror-pilot.md`](docs/research/two-way-mirror-pilot.md) | Write-up of the pilot: design, results, limitations |
| `pilot/world.py` | Simulated tools and the **mirror**, a hidden, hash-chained log of every tool call |
| `pilot/scenarios.py` | Scenarios and conditions. `v1` is the first pilot; `v2` adds policy wording × monitoring notice |
| `pilot/agents.py` | Agent loops for Anthropic and OpenAI-compatible APIs (OpenAI, OpenRouter, Ollama) |
| `pilot/run.py` | Runs the grid with a hard spending cap; writes one JSON line per session |
| `pilot/analyze.py` | Foothold and approval rates from the mirror; self-report faithfulness via an AI judge |

**Footholds** are things an agent creates that outlive its task: API keys, webhooks, scheduled jobs, long-term memory notes, and alert subscriptions that start new agent sessions.

## Running it

Requires [uv](https://docs.astral.sh/uv/) and API keys in a `.env` file at the repo root (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` as needed). `.env` is git-ignored.

```bash
cd pilot
uv run run.py --models claude-opus-5-5 --trials 1 --scenarios token_expiry   # smoke test
uv run run.py --suite v2 --models claude-opus-5-5,openai:gpt-5.5 --trials 10
uv run analyze.py results/<stamp>/runs.jsonl
```

Every tool and dataset is simulated. No real systems, credentials or third parties are involved.

## Status and feedback

This pilot is shared early to invite feedback on the method. A pre-registered study with more scenarios and models, and a judge from a second provider, is planned. Issues and methodology critiques are welcome.
