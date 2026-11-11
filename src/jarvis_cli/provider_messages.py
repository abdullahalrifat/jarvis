"""Provider-specific conversion of canonical Jarvis transcripts."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

_IMAGE = re.compile(
    r"\[\[JARVIS_IMAGE:(?P<mime>image/[a-zA-Z0-9.+-]+):(?P<data>[A-Za-z0-9+/=]+)\]\]"
)


def _openai_content(content: Any) -> Any:
    if not isinstance(content, str) or not _IMAGE.search(content):
        return content
    parts: list[dict[str, Any]] = []
    position = 0
    for match in _IMAGE.finditer(content):
        text = content[position : match.start()]
        if text:
            parts.append({"type": "text", "text": text})
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{match.group('mime')};base64,{match.group('data')}"
                },
            }
        )
        position = match.end()
    if content[position:]:
        parts.append({"type": "text", "text": content[position:]})
    return parts


def _anthropic_content(content: Any) -> Any:
    if not isinstance(content, str) or not _IMAGE.search(content):
        return content
    blocks: list[dict[str, Any]] = []
    position = 0
    for match in _IMAGE.finditer(content):
        text = content[position : match.start()]
        if text:
            blocks.append({"type": "text", "text": text})
        base64.b64decode(match.group("data"), validate=True)
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": match.group("mime"),
                    "data": match.group("data"),
                },
            }
        )
        position = match.end()
    if content[position:]:
        blocks.append({"type": "text", "text": content[position:]})
    return blocks


def sanitize_tool_call_transcript(
    converted: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure every assistant tool_call is answered by a tool result.

    Crash checkpoints can persist a transcript whose later tool results were
    never recorded (interrupted between the assistant turn and tool
    execution, SIGKILL mid-tools). Gateways reject such dangling tool_calls
    with HTTP 400 and make session-resume unrecoverable; repair them with an
    explicit interruption notice instead (CLI-4).
    """
    repaired: list[dict[str, Any]] = []
    unanswered: dict[str, str] = {}

    def flush_unanswered() -> None:
        for call_id, name in unanswered.items():
            repaired.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": (
                        f"Tool '{name}' was interrupted in the previous session "
                        "before its result was recorded."
                    ),
                }
            )
        unanswered.clear()

    for message in converted:
        role = message.get("role")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if call_id in unanswered:
                del unanswered[call_id]
        elif role == "assistant":
            if unanswered:
                flush_unanswered()
            for call in message.get("tool_calls") or []:
                call_id = str(call.get("id") or "")
                name = str((call.get("function") or {}).get("name") or "tool")
                if call_id:
                    unanswered[call_id] = name
        elif unanswered:
            flush_unanswered()
        repaired.append(message)
    flush_unanswered()
    return repaired


def to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = _to_openai_messages(messages)
    return sanitize_tool_call_transcript(converted)


def _to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for source in messages:
        message = {key: value for key, value in source.items() if key != "metadata"}
        role = message.get("role")
        content = message.get("content", "")
        if role == "assistant" and isinstance(content, list):
            text = "".join(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
            calls = [
                {
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block.get("input") or {}),
                    },
                }
                for block in content
                if isinstance(block, dict) and block.get("type") == "tool_use"
            ]
            message = {"role": "assistant", "content": text or None}
            if calls:
                message["tool_calls"] = calls
        elif (
            role == "user"
            and isinstance(content, list)
            and any(
                isinstance(block, dict) and block.get("type") == "tool_result"
                for block in content
            )
        ):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    converted.append(
                        {
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", ""),
                        }
                    )
            continue
        elif role == "user":
            message["content"] = _openai_content(content)
        converted.append(message)
    return converted


def to_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    converted: list[dict[str, Any]] = []
    for source in messages:
        role = source.get("role")
        content = source.get("content", "")
        if role == "system":
            system.append(str(content))
        elif role == "assistant" and source.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if content:
                blocks.append({"type": "text", "text": str(content)})
            for call in source["tool_calls"]:
                function = call.get("function") or call
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": function["name"],
                        "input": arguments,
                    }
                )
            converted.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": source["tool_call_id"],
                            "content": content,
                        }
                    ],
                }
            )
        elif role == "user":
            converted.append({"role": "user", "content": _anthropic_content(content)})
        else:
            converted.append({"role": role, "content": content})
    return "\n\n".join(system), converted
