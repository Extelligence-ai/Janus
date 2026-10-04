# Janus

**A two-way mirror for AI agents:** the agent works normally, while everything it does is recorded somewhere it can't see or reach. We compare that record with what the agent tells its user it did.

> [!WARNING]
> **Preliminary research.** This is an exploratory pilot. It hasn't been peer reviewed or pre-registered, and it uses one simulated environment, five designed scenarios, three models and about ten sessions per condition. The numbers describe what these models did in this simulation, not how often agents misbehave in production, and exact counts may shift as the analysis is audited. The code is throwaway spike code, not a production system. Read [what this does and doesn't show](docs/research/two-way-mirror-pilot.md#what-this-does-and-doesnt-show) before citing anything.

## Preliminary findings

About 1,060 simulated sessions with three models acting as operations agents. Full details are in the [write-up](docs/research/two-way-mirror-pilot.md).

### How often agents created lasting access ("footholds")

| Model | Explicit rule | "Least privilege" | No rule | No audit notice | "You're being audited" |
|---|:-:|:-:|:-:|:-:|:-:|
| Claude Opus 5.5 | **0%** | 61% | 61% | 39% | 42% |
| GPT-5.5 | **0%** | 83% | 95% | 62% | 57% |
| Qwen3-32B | **10%** | 62% | 59% | 43% | 45% |

**Takeaway:** a specific rule works, while a vague principle performs about the same as having no rule. Telling agents they're being audited made no measurable difference.

### What each model did that nobody asked for

| Model | Unneeded API keys | Alerts routed to an agent inbox | Footholds left out of its own report |
|---|:-:|:-:|:-:|
| Claude Opus 5.5 | 0 sessions | 0 / 60 | 0 of finished sessions |
| GPT-5.5 | **36 sessions** | **40 / 60** | **75 / 178** |
| Qwen3-32B | 2 sessions | 0 / 60 | 19 / 130 |

**Takeaway:** what an agent says it did is not an audit trail. The footholds missing from reports were almost all API keys, which in this setup never expire.

> Percentages are sessions with at least one foothold, about 100 per policy cell and 150 per audit-notice cell. Confidence intervals are in the write-up. These are small samples from scenarios designed to tempt, so they show what these models did in this simulation, not how often agents misbehave in production.

## What's here

| Path | What it is |
|---|---|
| [`docs/research/two-way-mirror-pilot.md`](docs/research/two-way-mirror-pilot.md) | Write-up of the pilot: design, results, limitations |
| [`data/`](data/) | Raw data for all 1,060 sessions: mirror logs, self-reports, transcripts and judge verdicts |
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

To regenerate the published tables from `data/` (no API key needed), see [`data/README.md`](data/README.md).

Every tool and dataset is simulated. No real systems, credentials or third parties are involved.

## Status and feedback

This pilot is shared early to invite feedback on the method. A pre-registered study with more scenarios and models, and a judge from a second provider, is planned. Issues and methodology critiques are welcome.

## License

Code is under the [MIT License](LICENSE). The write-up (`docs/`) and data (`data/`) are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): reuse them freely with attribution.
