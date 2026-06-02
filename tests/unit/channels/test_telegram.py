"""Tests for the Telegram channel."""

import asyncio

import pytest

from termcoder.channels.telegram import TelegramChannel, _PendingPermission
from termcoder.config import ConfigError
from termcoder.events import TextDelta, TurnComplete
from termcoder.models import PermissionDecision, ToolCall


async def test_confirm_tool_allows_from_connected_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = TelegramChannel(token="123:ABC")
    sent: list[tuple[int, str]] = []

    async def send_to_chat(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(channel, "_send_to_chat", send_to_chat)
    channel._active_chat_id = 42

    task = asyncio.create_task(
        channel.confirm_tool(ToolCall(id="call-1", name="bash", arguments='{"cmd":"pwd"}'))
    )
    await asyncio.sleep(0)

    assert await channel._resolve_permission(42, "yes") is True
    assert await task == "allow"
    assert sent == [
        (
            42,
            'tool permission requested: bash {"cmd":"pwd"}\nReply yes to allow or no to deny.',
        )
    ]


async def test_confirm_tool_denies_without_active_chat() -> None:
    channel = TelegramChannel(token="123:ABC")

    decision = await channel.confirm_tool(ToolCall(id="call-1", name="bash", arguments="{}"))

    assert decision == "deny"


async def test_permission_answer_from_other_chat_is_not_consumed() -> None:
    channel = TelegramChannel(token="123:ABC")
    future: asyncio.Future[PermissionDecision] = asyncio.get_running_loop().create_future()
    channel._pending_permission = _PendingPermission(chat_id=42, future=future)

    consumed = await channel._resolve_permission(7, "yes")

    assert consumed is False
    assert not future.done()


async def test_configured_chat_accepts_only_matching_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = TelegramChannel(token="123:ABC", allowed_chat_id=42)
    sent: list[tuple[int, str]] = []

    async def send_to_chat(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(channel, "_send_to_chat", send_to_chat)

    assert await channel._accept_chat(7) is False
    assert channel._chat_id is None
    assert await channel._accept_chat(42) is True
    assert channel._chat_id == 42
    assert sent == [(7, "termcoder is not configured for this chat.")]


async def test_unconfigured_chat_still_claims_first_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = TelegramChannel(token="123:ABC")
    sent: list[tuple[int, str]] = []

    async def send_to_chat(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(channel, "_send_to_chat", send_to_chat)

    assert await channel._accept_chat(42) is True
    assert await channel._accept_chat(7) is False
    assert sent == [(7, "termcoder is already connected to another chat.")]


async def test_render_event_batches_text_until_turn_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = TelegramChannel(token="123:ABC")
    sent: list[tuple[int, str]] = []

    async def send_to_chat(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(channel, "_send_to_chat", send_to_chat)
    channel._active_chat_id = 42

    await channel.render_event(TextDelta(text="hello"))
    await channel.render_event(TextDelta(text=" world"))
    await channel.render_event(TurnComplete())

    assert sent == [(42, "hello world")]


def test_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        TelegramChannel()
