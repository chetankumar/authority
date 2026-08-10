"""AIOrchestrator — single entry for model calls (doc 05).

Feature services never build LangChain models themselves. They call:
  invoke_once       — git suggest, simple one-shots
  invoke_structured — enrichment-style JSON answers
  invoke_stream     — chat / AI-jobs with tools + token callbacks
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.models.proposal import Proposal
from app.models.settings import ModelConfig
from app.services.ai_tools.accumulator import ProposalAccumulator
from app.services.model_factory import KeyResolutionError, ModelFactory

log = logging.getLogger("authority.ai")

TokenCallback = Callable[[str], Awaitable[None] | None]
ToolCallback = Callable[[str, dict[str, Any], str], Awaitable[None] | None]
StatusCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

_MAX_TOOL_ROUNDS = 8
_REASONING_BLOCK_TYPES = frozenset({"reasoning", "thinking"})
_WAIT_HEARTBEAT_SEC = 3.0
_ARGS_PREVIEW_MAX = 200


def _args_preview(args: Any) -> str:
    if not args:
        return ""
    try:
        text = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(args)
    if len(text) > _ARGS_PREVIEW_MAX:
        return text[: _ARGS_PREVIEW_MAX - 1] + "…"
    return text


@dataclass
class AssistantTurn:
    content: str = ""
    proposals: list[Proposal] = field(default_factory=list)
    error: str | None = None


class AIOrchestrator:
    def __init__(self) -> None:
        pass

    async def invoke_once(
        self,
        model_cfg: ModelConfig,
        messages: list[Any],
        *,
        timeout: float | None = 60.0,
    ) -> str:
        import asyncio

        model = ModelFactory.build(model_cfg)
        coro = model.ainvoke(messages)
        if timeout is not None:
            response = await asyncio.wait_for(coro, timeout=timeout)
        else:
            response = await coro
        return _content_text(response)

    async def invoke_structured(
        self,
        model_cfg: ModelConfig,
        messages: list[Any],
        *,
        timeout: float | None = 90.0,
    ) -> str:
        """Same as invoke_once; caller parses structured output."""
        return await self.invoke_once(model_cfg, messages, timeout=timeout)

    async def invoke_stream(
        self,
        model_cfg: ModelConfig,
        messages: list[Any],
        tools: list[Any] | None = None,
        accumulator: ProposalAccumulator | None = None,
        *,
        on_token: TokenCallback | None = None,
        on_tool: ToolCallback | None = None,
        on_status: StatusCallback | None = None,
    ) -> AssistantTurn:
        """Stream an assistant turn; run tool loops server-side.

        ``on_token`` receives answer text and (when present) reasoning deltas so
        the UI is not blank during long think/tool phases. Only answer text is
        collected into the persisted assistant message. Propose tools append to
        ``accumulator``.
        """
        acc = accumulator or ProposalAccumulator()
        try:
            model = ModelFactory.build(model_cfg)
        except KeyResolutionError as exc:
            return AssistantTurn(error=str(exc))
        except Exception as exc:
            return AssistantTurn(error=f"Couldn't build the model: {exc}")

        bound = model.bind_tools(tools) if tools else model
        working = list(messages)
        collected = ""

        try:
            for round_i in range(_MAX_TOOL_ROUNDS):
                chunk_text, tool_calls, ai_message = await self._stream_round(
                    bound, working, on_token=on_token, on_status=on_status
                )
                collected += chunk_text
                if not tool_calls:
                    break

                kwargs = getattr(ai_message, "additional_kwargs", None) or {}
                if not chunk_text.strip():
                    log.info(
                        "stream round %s: %d tool call(s), no answer text "
                        "(UI silent until follow-up unless reasoning streamed)",
                        round_i,
                        len(tool_calls),
                    )
                if kwargs.get("reasoning_content") or kwargs.get("reasoning_details"):
                    log.info(
                        "stream round %s: reasoning metadata present for tool follow-up",
                        round_i,
                    )

                from langchain_core.messages import ToolMessage

                working.append(ai_message)
                for call in tool_calls:
                    name = call.get("name") or ""
                    args = call.get("args") or {}
                    call_id = call.get("id") or name
                    if on_status:
                        preview = _args_preview(args if isinstance(args, dict) else {})
                        maybe = on_status(
                            {"phase": "tool", "name": name, "argsPreview": preview}
                        )
                        if maybe is not None:
                            await maybe
                    result = await self._execute_tool(tools or [], name, args)
                    if on_tool:
                        maybe = on_tool(name, args if isinstance(args, dict) else {}, result)
                        if maybe is not None:
                            await maybe
                    working.append(ToolMessage(content=result, tool_call_id=call_id))
                # Continue loop for follow-up after tools.
            return AssistantTurn(content=collected.strip(), proposals=acc.all())
        except Exception as exc:
            log.exception("invoke_stream failed")
            return AssistantTurn(content=collected.strip(), proposals=acc.all(), error=str(exc))

    async def _stream_round(
        self,
        model: Any,
        messages: list[Any],
        *,
        on_token: TokenCallback | None,
        on_status: StatusCallback | None = None,
    ) -> tuple[str, list[dict[str, Any]], Any]:
        """Stream one model round. Returns (answer_text, tool_calls, final AIMessage)."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        text_parts: list[str] = []
        last_chunk: Any = None
        # Cumulative reasoning tracker for delta extraction across chunks.
        reasoning_seen = [""]
        announced_thinking = False
        got_piece = False
        round_started = time.monotonic()
        heartbeat_stop = asyncio.Event()
        heartbeat_task: asyncio.Task[None] | None = None

        async def heartbeat_loop() -> None:
            while not heartbeat_stop.is_set():
                try:
                    await asyncio.wait_for(heartbeat_stop.wait(), timeout=_WAIT_HEARTBEAT_SEC)
                    return
                except asyncio.TimeoutError:
                    if on_status and not got_piece:
                        elapsed = int(time.monotonic() - round_started)
                        maybe = on_status({"phase": "waiting", "elapsedSec": elapsed})
                        if maybe is not None:
                            await maybe

        if on_status:
            heartbeat_task = asyncio.create_task(heartbeat_loop())

        async def _emit_stream_piece(piece: str, *, answer: bool) -> None:
            nonlocal announced_thinking, got_piece
            if not piece:
                return
            got_piece = True
            if answer:
                text_parts.append(piece)
            elif not announced_thinking:
                announced_thinking = True
                if on_status:
                    maybe = on_status({"phase": "thinking"})
                    if maybe is not None:
                        await maybe
            if on_token:
                maybe = on_token(piece)
                if maybe is not None:
                    await maybe

        # Prefer astream when available.
        if hasattr(model, "astream"):
            try:
                async for chunk in model.astream(messages):
                    last_chunk = chunk if last_chunk is None else last_chunk + chunk
                    answer = _content_text(chunk)
                    if answer:
                        await _emit_stream_piece(answer, answer=True)
                    reasoning = _reasoning_delta(chunk, reasoning_seen)
                    if reasoning:
                        await _emit_stream_piece(reasoning, answer=False)
            finally:
                heartbeat_stop.set()
                if heartbeat_task is not None:
                    await heartbeat_task
            if last_chunk is None:
                # Empty stream — fall back to ainvoke.
                response = await model.ainvoke(messages)
                text = _content_text(response)
                if text and on_token:
                    maybe = on_token(text)
                    if maybe is not None:
                        await maybe
                return text, _tool_calls(response), response

            # Gather tool calls from aggregated chunk / message.
            ai_msg = last_chunk if isinstance(last_chunk, (AIMessage, AIMessageChunk)) else AIMessage(
                content="".join(text_parts)
            )
            # Convert chunk aggregate to AIMessage for tool loop — keep
            # additional_kwargs (reasoning_content / reasoning_details) so
            # OpenRouter/DeepSeek tool follow-ups stay valid.
            if isinstance(ai_msg, AIMessageChunk):
                ai_msg = AIMessage(
                    content=ai_msg.content,
                    tool_calls=getattr(ai_msg, "tool_calls", None) or [],
                    id=getattr(ai_msg, "id", None),
                    additional_kwargs=dict(getattr(ai_msg, "additional_kwargs", None) or {}),
                    response_metadata=dict(getattr(ai_msg, "response_metadata", None) or {}),
                )
            tool_calls = _tool_calls(ai_msg)
            return "".join(text_parts), tool_calls, ai_msg

        response = await model.ainvoke(messages)
        text = _content_text(response)
        if text and on_token:
            maybe = on_token(text)
            if maybe is not None:
                await maybe
        elif on_token:
            reasoning = _reasoning_delta(response, reasoning_seen)
            if reasoning:
                if on_status:
                    maybe = on_status({"phase": "thinking"})
                    if maybe is not None:
                        await maybe
                maybe = on_token(reasoning)
                if maybe is not None:
                    await maybe
        return text, _tool_calls(response), response

    async def _execute_tool(self, tools: list[Any], name: str, args: Any) -> str:
        tool = next((t for t in tools if getattr(t, "name", None) == name), None)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            raw_args = args if isinstance(args, dict) else {}
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(raw_args)
            else:
                result = tool.invoke(raw_args)
            return result if isinstance(result, str) else str(result)
        except Exception as exc:
            log.warning("tool %s failed: %s", name, exc)
            return f"Tool error: {exc}"


def _content_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                btype = block.get("type")
                if btype == "text":
                    parts.append(str(block.get("text", "")))
                # Skip reasoning/thinking blocks here — those go through _reasoning_delta.
            elif hasattr(block, "text") and getattr(block, "type", None) not in _REASONING_BLOCK_TYPES:
                parts.append(str(block.text))
        return "".join(parts)
    return str(content) if content is not None else ""


def _reasoning_delta(response: Any, seen: list[str]) -> str:
    """Extract newly visible reasoning text from a chunk or message.

    ``seen[0]`` tracks cumulative ``reasoning_content`` so we only emit deltas.
    Reasoning is for live UI feedback; it is not part of the saved answer.
    """
    parts: list[str] = []

    kwargs = getattr(response, "additional_kwargs", None) or {}
    rc = kwargs.get("reasoning_content")
    if isinstance(rc, str) and rc:
        prev = seen[0]
        if rc.startswith(prev):
            delta = rc[len(prev) :]
            seen[0] = rc
            if delta:
                parts.append(delta)
        else:
            # Fresh fragment (not a growing prefix) — append as delta.
            seen[0] = prev + rc
            parts.append(rc)
    else:
        # Only use reasoning_details when reasoning_content isn't on the chunk —
        # merged lists can otherwise re-emit prior fragments.
        details = kwargs.get("reasoning_details")
        if isinstance(details, list):
            for entry in details:
                if isinstance(entry, dict):
                    text = entry.get("text") or entry.get("content") or entry.get("summary")
                    if isinstance(text, str) and text:
                        parts.append(text)
                elif isinstance(entry, str) and entry:
                    parts.append(entry)

    content = getattr(response, "content", None)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") in _REASONING_BLOCK_TYPES:
                text = block.get("text") or block.get("reasoning") or block.get("thinking")
                if isinstance(text, str) and text:
                    parts.append(text)
            elif hasattr(block, "type") and getattr(block, "type", None) in _REASONING_BLOCK_TYPES:
                text = getattr(block, "text", None) or getattr(block, "reasoning", None)
                if text:
                    parts.append(str(text))

    return "".join(parts)


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None) or []
    out: list[dict[str, Any]] = []
    for c in calls:
        if isinstance(c, dict):
            out.append(c)
        else:
            out.append(
                {
                    "name": getattr(c, "name", ""),
                    "args": getattr(c, "args", {}) or {},
                    "id": getattr(c, "id", "") or "",
                }
            )
    return out
