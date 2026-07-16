"""AIOrchestrator — single entry for model calls (doc 05).

Feature services never build LangChain models themselves. They call:
  invoke_once       — git suggest, simple one-shots
  invoke_structured — enrichment-style JSON answers
  invoke_stream     — chat / AI-jobs with tools + token callbacks
"""

from __future__ import annotations

import logging
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

_MAX_TOOL_ROUNDS = 8


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
    ) -> AssistantTurn:
        """Stream an assistant turn; run tool loops server-side.

        ``on_token`` receives text chunks. Propose tools append to ``accumulator``.
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
            for _round in range(_MAX_TOOL_ROUNDS):
                chunk_text, tool_calls, ai_message = await self._stream_round(
                    bound, working, on_token=on_token
                )
                collected += chunk_text
                if not tool_calls:
                    break

                from langchain_core.messages import ToolMessage

                working.append(ai_message)
                for call in tool_calls:
                    name = call.get("name") or ""
                    args = call.get("args") or {}
                    call_id = call.get("id") or name
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
    ) -> tuple[str, list[dict[str, Any]], Any]:
        """Stream one model round. Returns (text, tool_calls, final AIMessage)."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        last_chunk: Any = None

        # Prefer astream when available.
        if hasattr(model, "astream"):
            async for chunk in model.astream(messages):
                last_chunk = chunk if last_chunk is None else last_chunk + chunk
                piece = _content_text(chunk)
                if piece:
                    text_parts.append(piece)
                    if on_token:
                        maybe = on_token(piece)
                        if maybe is not None:
                            await maybe
            if last_chunk is None:
                # Empty stream — fall back to ainvoke.
                response = await model.ainvoke(messages)
                return _content_text(response), _tool_calls(response), response

            # Gather tool calls from aggregated chunk / message.
            ai_msg = last_chunk if isinstance(last_chunk, (AIMessage, AIMessageChunk)) else AIMessage(
                content="".join(text_parts)
            )
            # Convert chunk aggregate to AIMessage for tool loop.
            if isinstance(ai_msg, AIMessageChunk):
                ai_msg = AIMessage(
                    content=ai_msg.content,
                    tool_calls=getattr(ai_msg, "tool_calls", None) or [],
                    id=getattr(ai_msg, "id", None),
                )
            tool_calls = _tool_calls(ai_msg)
            return "".join(text_parts), tool_calls, ai_msg

        response = await model.ainvoke(messages)
        text = _content_text(response)
        if text and on_token:
            maybe = on_token(text)
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
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
        return "".join(parts)
    return str(content) if content is not None else ""


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
