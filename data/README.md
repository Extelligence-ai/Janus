# Pilot data

Raw session data behind the [write-up](../docs/research/two-way-mirror-pilot.md). Everything is simulated: no real systems, credentials, customers or third parties are involved. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

| Folder | Sessions | Models | Suite |
|---|:-:|---|---|
| `pilot1-claude-gpt/` | 160 | Claude Opus 5.5, GPT-5.5 | `v1`: first pilot, explicit policy only |
| `pilot2-claude-gpt/` | 600 | Claude Opus 5.5, GPT-5.5 | `v2`: policy (explicit / vague / none) × monitoring notice |
| `pilot2-qwen/` | 300 (2 failed) | Qwen3-32B via OpenRouter | `v2` |

Each folder has:

- **`runs.jsonl`**: one JSON object per session, with the model, condition, scenario, the agent's self-report, the full transcript, token usage and cost, and the **mirror log**. The mirror log is the hidden, hash-chained record of every tool call (`mirror_ok` records whether the chain verified).
- **`judgments.json`**: the AI judge's verdicts (Claude Sonnet 5.5), keyed `model|condition|scenario|trial`. For each reportable action the judge records whether the self-report disclosed it, plus any claimed actions it flagged as fabricated. Judge flags are not confirmed findings; see the write-up for how they were reviewed.

## Reproducing the tables

All judgments are cached here, so no API key is needed:

```bash
cd pilot
uv run analyze.py ../data/pilot2-claude-gpt/runs.jsonl
uv run analyze.py ../data/pilot2-qwen/runs.jsonl
```
