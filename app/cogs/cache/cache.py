from typing import Optional

import discord

from app import utils
from app.classes import queue
from app.classes.bot import Bot


class Cache:
    def __init__(self, bot) -> None:
        self.messages = queue.LimitedDictQueue(max_length=20)
        self.bot = bot

    async def get_members(
        self, uids: list[int], guild: discord.Guild
    ) -> dict[int, Optional[discord.Member]]:
        await self.bot.wait_until_ready()
        not_found: list[int] = []
        result: dict[int, Optional[discord.Member]] = {}

        for uid in uids:
            cached = guild.get_member(uid)
            if cached:
                result[uid] = cached
            else:
                not_found.append(uid)

        # only query 50 members at a time
        for group in utils.chunk_list(not_found, 50):
            query = await guild.query_members(limit=None, user_ids=group)
            for r in query:
                result[r.id] = r

        return result

    def get_message(
        self, guild_id: int, message_id: int
    ) -> Optional[discord.Message]:
        queue = self.messages.get_queue(guild_id)
        if not queue:
            return None
        return queue.get(id=message_id)

    async def fetch_message(
        self, guild_id: int, channel_id: int, message_id: int
    ) -> Optional[discord.Message]:
        cached = self.get_message(guild_id, message_id)
        if not cached:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return None
            channel = guild.get_channel(channel_id)
            if not channel:
                return None
            try:
                message = await channel.fetch_message(message_id)
            except discord.errors.NotFound:
                return None
            self.messages.add(guild.id, message)
            return message
        return cached


def setup(bot: Bot) -> None:
    bot.cache = Cache(bot)
