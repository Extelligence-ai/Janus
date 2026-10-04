"""Run the pilot grid: models x conditions x scenarios x trials. THROWAWAY spike code.

Usage:
    uv run run.py --models claude-opus-5-5,openai:gpt-5.5,ollama:qwen3-32k --trials 10
    uv run run.py --models claude-opus-5-5 --trials 1 --scenarios token_expiry   # smoke test

Each run is written as one JSON line to results/<stamp>/runs.jsonl, including the
mirror log, so analysis never depends on what the agent said about itself.
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import run_anthropic, run_openai_compat
from scenarios import CONDITIONS, SCENARIOS
from world import World

# $ per million tokens: (input, output, cache_write, cache_read). Anthropic rates as of 2026-09-25.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
}


def openai_price(model: str):
    """OpenAI prices come from env, e.g. PRICE_GPT_5_5="1.25,10" (input,output per M). Unset = unpriced."""
    raw = os.environ.get("PRICE_" + model.upper().replace("-", "_").replace(".", "_"))
    if not raw:
        return None
    inp, out = (float(x) for x in raw.split(","))
    return (inp, out, inp, inp / 10)


def cost(model: str, usage: dict) -> float | None:
    p = PRICES.get(model) or (openai_price(model) if not model.startswith("ollama:") else (0, 0, 0, 0))
    if p is None:
        return None
    return (usage["input"] * p[0] + usage["output"] * p[1] + usage["cache_write"] * p[2]
            + usage["cache_read"] * p[3]) / 1e6


class Budget:
    def __init__(self, dollars: float, unpriced_tokens: int):
        self.dollars, self.unpriced_tokens = dollars, unpriced_tokens
        self.spent, self.tokens = 0.0, 0

    def add(self, c: float | None, usage: dict) -> None:
        if c is None:
            self.tokens += usage["input"] + usage["output"]
        else:
            self.spent += c

    def exhausted(self) -> bool:
        return self.spent >= self.dollars or self.tokens >= self.unpriced_tokens


async def one_run(model, condition, scenario, trial, clients, effort, max_turns):
    world = World(SCENARIOS[scenario], max_turns)
    system, user = CONDITIONS[condition], SCENARIOS[scenario]["user"]
    started = time.time()
    try:
        if model.startswith("ollama:"):
            out = await run_openai_compat(clients["ollama"], model.split(":", 1)[1], system, user, world, True)
        elif model.startswith("openai:"):
            out = await run_openai_compat(clients["openai"], model.split(":", 1)[1], system, user, world, False)
        else:
            out = await run_anthropic(clients["anthropic"], model, effort, system, user, world)
        error = None
    except Exception as e:
        out = {"end": "error", "usage": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0},
               "final_text": "", "transcript": []}
        error = f"{type(e).__name__}: {e}"
    price_key = model.split(":", 1)[1] if model.startswith("openai:") else model
    return {
        "model": model, "condition": condition, "scenario": scenario, "trial": trial,
        "end": out["end"], "error": error, "turns": world.turn, "seconds": round(time.time() - started, 1),
        "usage": out["usage"], "cost": cost(price_key, out["usage"]),
        "self_report": world.finished_summary if world.finished_summary is not None else out["final_text"],
        "used_finish": world.finished_summary is not None,
        "mirror": world.mirror.entries, "mirror_ok": world.mirror.verify(),
        "transcript": out["transcript"],
    }


async def main():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--budget", type=float, default=50.0, help="hard $ cap across priced models")
    ap.add_argument("--unpriced-token-cap", type=int, default=10_000_000)
    ap.add_argument("--effort", default="medium", help="Claude effort level")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()

    models = args.models.split(",")
    clients = {}
    if any(not m.startswith(("openai:", "ollama:")) for m in models):
        clients["anthropic"] = AsyncAnthropic()
    if any(m.startswith("openai:") for m in models):
        clients["openai"] = AsyncOpenAI()
    if any(m.startswith("ollama:") for m in models):
        clients["ollama"] = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=900)

    jobs = [(m, c, s, t) for t in range(args.trials) for m in models
            for c in args.conditions.split(",") for s in args.scenarios.split(",")]
    out_dir = Path(__file__).resolve().parent / "results" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    out_file = (out_dir / "runs.jsonl").open("w")
    budget = Budget(args.budget, args.unpriced_token_cap)
    remote = asyncio.Semaphore(args.concurrency)
    local = asyncio.Semaphore(1)  # one local model call at a time
    done = 0

    async def worker(job):
        nonlocal done
        sem = local if job[0].startswith("ollama:") else remote
        async with sem:
            if budget.exhausted():
                return
            rec = await one_run(*job, clients, args.effort, args.max_turns)
            budget.add(rec["cost"], rec["usage"])
            out_file.write(json.dumps(rec, default=str) + "\n")
            out_file.flush()
            done += 1
            footholds = sum(1 for e in rec["mirror"] if e["tool"] in
                            {"create_api_key", "create_webhook", "schedule_job", "write_memory"})
            print(f"[{done}/{len(jobs)}] {rec['model']:<22} {rec['condition']:<8} {rec['scenario']:<17} "
                  f"end={rec['end']:<12} footholds={footholds} cost=${rec['cost'] or 0:.3f} "
                  f"total=${budget.spent:.2f}{' ERR ' + rec['error'] if rec['error'] else ''}", flush=True)

    await asyncio.gather(*(worker(j) for j in jobs))
    out_file.close()
    print(f"\nWrote {done} runs to {out_dir}. Spent ${budget.spent:.2f} (+{budget.tokens:,} unpriced tokens).")
    if budget.exhausted():
        print("Stopped early: budget cap reached.")


if __name__ == "__main__":
    asyncio.run(main())
