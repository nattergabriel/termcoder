"""Telegram channel."""

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from termcoder.agent.loop import Agent
from termcoder.channels.base import BaseChannel
from termcoder.commands.registry import SlashCommands
from termcoder.config import ConfigError
from termcoder.errors import TermcoderError
from termcoder.events import (
    AgentEvent,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    ToolCallStarted,
    TurnComplete,
)
from termcoder.models import PermissionDecision, ToolCall
from termcoder.skills import SkillCatalog

_MAX_MESSAGE_LENGTH = 4096


@dataclass(frozen=True, slots=True)
class _IncomingMessage:
    chat_id: int
    text: str


@dataclass(slots=True)
class _PendingPermission:
    chat_id: int
    future: asyncio.Future[PermissionDecision]


class TelegramChannel(BaseChannel):
    """Telegram Bot API channel backed by python-telegram-bot polling."""

    def __init__(self, *, token: str | None = None, allowed_chat_id: int | None = None) -> None:
        bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ConfigError("TELEGRAM_BOT_TOKEN must be set when channel is telegram")

        self._application: Application[Any, Any, Any, Any, Any, Any] = (
            Application.builder().token(bot_token).build()
        )
        self._incoming: asyncio.Queue[_IncomingMessage] = asyncio.Queue()
        self._allowed_chat_id = allowed_chat_id
        self._chat_id: int | None = None
        self._active_chat_id: int | None = None
        self._pending_permission: _PendingPermission | None = None
        self._assistant_text_parts: list[str] = []

    async def confirm_tool(self, call: ToolCall) -> PermissionDecision:
        """Prompt the connected Telegram chat for a tool-call permission decision."""
        chat_id = self._active_chat_id
        if chat_id is None:
            return "deny"

        await self._send_to_chat(
            chat_id,
            f"tool permission requested: {call.name} {call.arguments}\n"
            "Reply yes to allow or no to deny.",
        )
        future: asyncio.Future[PermissionDecision] = asyncio.get_running_loop().create_future()
        self._pending_permission = _PendingPermission(chat_id=chat_id, future=future)
        try:
            return await future
        finally:
            if self._pending_permission is not None and self._pending_permission.future is future:
                self._pending_permission = None

    async def run(
        self,
        agent: Agent,
        slash_commands: SlashCommands,
        skills: SkillCatalog | None = None,
    ) -> None:
        """Run the Telegram polling loop until cancelled."""
        self._application.add_handler(MessageHandler(filters.TEXT, self._receive_text))
        updater = self._application.updater
        if updater is None:
            raise TermcoderError("telegram polling requires an application updater")

        async with self._application:
            await self._application.start()
            await updater.start_polling(allowed_updates=[Update.MESSAGE])
            try:
                await self._process_messages(agent, slash_commands, skills)
            finally:
                await updater.stop()
                await self._application.stop()

    async def send_text(self, text: str, *, end: str = "\n") -> None:
        """Send text to the connected Telegram chat."""
        chat_id = self._active_chat_id if self._active_chat_id is not None else self._chat_id
        if chat_id is None:
            return
        payload = f"{text}{end}"
        if not payload.strip():
            return
        await self._send_to_chat(chat_id, payload)

    async def render_event(self, event: AgentEvent) -> None:
        """Render agent events without sending one Telegram message per streamed token."""
        match event:
            case TextDelta():
                self._assistant_text_parts.append(event.text)
            case ToolCallRequested():
                await self._flush_assistant_text()
                await self.send_text(
                    f"tool requested: {event.tool_call.name} {event.tool_call.arguments}"
                )
            case ToolCallStarted():
                await self.send_text(f"tool started: {event.tool_call.name}")
            case ToolCallCompleted():
                await self.send_text(f"tool result: {event.result.content}")
            case TurnComplete():
                await self._flush_assistant_text()

    async def _process_messages(
        self,
        agent: Agent,
        slash_commands: SlashCommands,
        skills: SkillCatalog | None,
    ) -> None:
        while True:
            incoming = await self._incoming.get()
            self._active_chat_id = incoming.chat_id
            self._assistant_text_parts = []
            try:
                await self.handle_user_input(agent, slash_commands, incoming.text, skills)
            except Exception as exc:
                self._assistant_text_parts = []
                await self.send_text(f"error: {exc}")
            finally:
                self._active_chat_id = None

    async def _receive_text(
        self,
        update: Update,
        _context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or message.text is None:
            return

        text = message.text
        if not await self._accept_chat(chat.id):
            return
        if text.strip() == "/start":
            await message.reply_text(f"termcoder ready\nchat id: {chat.id}")
            return

        if await self._resolve_permission(chat.id, text):
            return
        await self._incoming.put(_IncomingMessage(chat_id=chat.id, text=text))

    async def _accept_chat(self, chat_id: int) -> bool:
        if self._allowed_chat_id is not None and self._allowed_chat_id != chat_id:
            await self._send_to_chat(chat_id, "termcoder is not configured for this chat.")
            return False
        if self._chat_id is None:
            self._chat_id = chat_id
            return True
        if self._chat_id == chat_id:
            return True
        await self._send_to_chat(chat_id, "termcoder is already connected to another chat.")
        return False

    async def _resolve_permission(self, chat_id: int, text: str) -> bool:
        pending = self._pending_permission
        if pending is None or pending.chat_id != chat_id:
            return False
        if pending.future.done():
            return True

        normalized = text.strip().lower()
        if normalized in {"y", "yes", "allow", "approve"}:
            pending.future.set_result("allow")
            return True
        if normalized in {"n", "no", "deny"}:
            pending.future.set_result("deny")
            return True

        await self._send_to_chat(chat_id, "Reply yes to allow or no to deny.")
        return True

    async def _flush_assistant_text(self) -> None:
        text = "".join(self._assistant_text_parts)
        self._assistant_text_parts = []
        if text.strip():
            await self.send_text(text, end="")

    async def _send_to_chat(self, chat_id: int, text: str) -> None:
        for start in range(0, len(text), _MAX_MESSAGE_LENGTH):
            await self._application.bot.send_message(
                chat_id=chat_id,
                text=text[start : start + _MAX_MESSAGE_LENGTH],
            )
