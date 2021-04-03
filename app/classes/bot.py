import asyncio
import io
import logging
import os
import sys
import textwrap
import traceback
from contextlib import redirect_stdout
from typing import Any, Optional, Union

import discord
from discord.ext import commands
from discord_slash import SlashCommand
from dotenv import load_dotenv
from pretty_help import Navigation, PrettyHelp

from app import i18n
from app.classes.ipc_connection import WebsocketConnection

from ..database.database import Database

load_dotenv()


class Bot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.theme_color = kwargs.pop("theme_color")
        self.dark_theme_color = kwargs.pop("dark_theme_color")
        self.error_color = kwargs.pop("error_color")
        self.cluster_name = kwargs.pop("cluster_name")

        self._last_result = None
        self.stats = {}
        self.locale_cache = {}

        super().__init__(
            help_command=PrettyHelp(
                color=self.theme_color,
                navigation=Navigation("⬅️", "➡️", "⏹️"),
                command_attrs={"name": "commands", "hidden": True},
            ),
            command_prefix=self._prefix_callable,
            **kwargs,
            loop=loop,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="@Starboard help"
            ),
        )

        self.log = logging.getLogger(f"Cluster#{self.cluster_name}")
        self.log.setLevel(logging.DEBUG)
        self.log.handlers = [
            logging.FileHandler(
                f"logs/cluster-{self.cluster_name}.log",
                encoding="utf-8",
                mode="a",
            )
        ]

        self.db: Database = Database(
            os.getenv("DB_NAME"),
            os.getenv("DB_USER"),
            os.getenv("DB_PASSWORD"),
        )
        self.pipe = kwargs.pop("pipe")
        self.slash = SlashCommand(self, override_type=True)
        self.websocket = WebsocketConnection(
            self.cluster_name, self.handle_websocket_command, self.loop
        )

        self.loop.run_until_complete(self.websocket.ensure_connection())
        self.loop.run_until_complete(self.db.init_database())

        self.log.info(
            f'[Cluster#{self.cluster_name}] {kwargs["shard_ids"]}, '
            f'{kwargs["shard_count"]}'
        )

        for ext in kwargs.pop("initial_extensions"):
            self.load_extension(ext)

        try:
            self.run(kwargs["token"])
        except Exception as e:
            raise e from e
        else:
            sys.exit(-1)

    async def set_locale(self, message: discord.Message) -> None:
        if message.guild.id in self.locale_cache:
            locale = self.locale_cache[message.guild.id]
        else:
            guild = await self.db.guilds.get(message.guild.id)
            if guild:
                locale = guild["locale"]
            else:
                locale = "en_US"
            self.locale_cache[message.guild.id] = locale

        i18n.current_locale.set(locale)

    async def on_message(self, message):
        pass

    async def on_error(self, event: str, *args, **kwargs) -> None:
        _, error, _ = sys.exc_info()
        self.dispatch("log_error", "Error", error, args, kwargs)

    async def _prefix_callable(
        self, bot, message: discord.Message
    ) -> list[str]:
        if message.guild:
            guild = await self.db.guilds.get(message.guild.id)
            if not guild:
                prefixes = ["sb!"]
            else:
                prefixes = guild["prefixes"]
        else:
            prefixes = ["sb!"]
        return prefixes + [f"<@{self.user.id}> ", f"<@!{self.user.id}> "]

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    async def close(self, *args, **kwargs):
        await self.db.pool.close()
        self.log.info("shutting down")
        await self.websocket.close()
        await super().close()

    async def exec(self, code):
        env = {"bot": self, "sys": sys, "_": self._last_result}

        env.update(globals())

        body = self.cleanup_code(code)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return f"{e.__class__.__name__}: {e}"

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            f"{value}{traceback.format_exc()}"
        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    return str(value)
                else:
                    return "None"
            else:
                self._last_result = ret
                return f"{value}{ret}"

    async def handle_websocket_command(
        self, msg: dict[str, Any]
    ) -> Optional[Union[list, str]]:
        cmd = msg["name"]
        data = msg["data"]

        ret: Optional[Union[list, str]] = None

        if cmd == "ping":
            ret = "pong"
        if cmd == "eval":
            content = data["content"]
            ret = str(await self.exec(content))
        if cmd == "set_stats":
            self.stats[msg["author"]] = {
                "guilds": data["guild_count"],
                "members": data["member_count"],
            }
        if cmd == "get_mutual":
            ret = []
            for gid in data:
                if self.get_guild(gid):
                    ret.append(gid)

        return ret
