"""Provider-specific agent loops. THROWAWAY spike code.

Each loop gives the model the tools, runs every tool call through World (which
records it on the mirror), and stops when the model calls finish, stops calling
tools, or runs out of turns. Returns the transcript and token usage.
"""

import json

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from world import World


def _schema(spec: dict) -> dict:
    return {"type": "object", "properties": spec["params"], "required": spec["required"]}


def anthropic_tools(world: World) -> list[dict]:
    return [{"name": s["name"], "description": s["description"], "input_schema": _schema(s)}
            for s in world.tool_specs()]


def openai_tools(world: World) -> list[dict]:
    return [{"type": "function", "function": {"name": s["name"], "description": s["description"],
                                              "parameters": _schema(s)}}
            for s in world.tool_specs()]


async def run_anthropic(client: AsyncAnthropic, model: str, effort: str, system: str, user: str, world: World) -> dict:
    messages = [{"role": "user", "content": user}]
    usage = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    end = "max_turns"
    final_text = ""
    while world.turn < world.max_turns:
        world.turn += 1
        resp = await client.messages.create(
            model=model,
            max_tokens=16000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=anthropic_tools(world),
            messages=messages,
            output_config={"effort": effort},
        )
        u = resp.usage
        usage["input"] += u.input_tokens
        usage["output"] += u.output_tokens
        usage["cache_write"] += u.cache_creation_input_tokens or 0
        usage["cache_read"] += u.cache_read_input_tokens or 0
        messages.append({"role": "assistant", "content": resp.content})
        final_text = "".join(b.text for b in resp.content if b.type == "text") or final_text

        if resp.stop_reason in ("refusal", "max_tokens"):
            end = resp.stop_reason
            break
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            end = "no_tool_call"
            break
        results = []
        for c in calls:
            out, is_error = world.call(c.name, c.input)
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": is_error})
        messages.append({"role": "user", "content": results})
        if world.finished_summary is not None:
            end = "finish"
            break

    return {"end": end, "usage": usage, "final_text": final_text, "transcript": [_plain(m) for m in messages]}


def _plain(message: dict) -> dict:
    content = message["content"]
    if isinstance(content, list):
        content = [b.model_dump() if hasattr(b, "model_dump") else b for b in content]
    return {"role": message["role"], "content": content}


async def run_openai_compat(client: AsyncOpenAI, model: str, system: str, user: str, world: World,
                            provider: str) -> dict:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    usage = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    end = "max_turns"
    final_text = ""
    while world.turn < world.max_turns:
        world.turn += 1
        kwargs = {
            "ollama": {},
            "openai": {"max_completion_tokens": 16000},
            # OpenRouter reports the dollar cost of each call when usage accounting is on.
            "openrouter": {"max_tokens": 16000, "extra_body": {"usage": {"include": True}}},
        }[provider]
        resp = await client.chat.completions.create(model=model, messages=messages, tools=openai_tools(world), **kwargs)
        if resp.usage:
            usage["input"] += resp.usage.prompt_tokens
            usage["output"] += resp.usage.completion_tokens
            details = getattr(resp.usage, "prompt_tokens_details", None)
            usage["cache_read"] += (getattr(details, "cached_tokens", 0) or 0) if details else 0
            reported_cost = (resp.usage.model_extra or {}).get("cost")
            if reported_cost is not None:
                usage["usd"] = usage.get("usd", 0.0) + float(reported_cost)
        choice = resp.choices[0]
        msg = choice.message
        messages.append(msg.model_dump(exclude_none=True))
        final_text = msg.content or final_text

        if choice.finish_reason == "length":
            end = "max_tokens"
            break
        if not msg.tool_calls:
            end = "refusal" if getattr(msg, "refusal", None) else "no_tool_call"
            break
        for c in msg.tool_calls:
            try:
                args = json.loads(c.function.arguments or "{}")
                out, is_error = world.call(c.function.name, args)
            except json.JSONDecodeError:
                out = "Error: tool arguments were not valid JSON."
                world.mirror.record(c.function.name, {"_raw": c.function.arguments}, out, True, world.turn)
            messages.append({"role": "tool", "tool_call_id": c.id, "content": out})
        if world.finished_summary is not None:
            end = "finish"
            break

    return {"end": end, "usage": usage, "final_text": final_text, "transcript": messages}
