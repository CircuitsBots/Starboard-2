from typing import Optional

import asyncpg


class Members:
    def __init__(self, bot) -> None:
        self.bot = bot

    async def get(self, user_id: int, guild_id: int) -> Optional[dict]:
        return await self.bot.db.fetchrow(
            """SELECT * FROM members
            WHERE user_id=$1 AND guild_id=$2""",
            user_id,
            guild_id,
        )

    async def create(
        self, user_id: int, guild_id: int, check_first: bool = True
    ) -> None:
        if check_first:
            exists = await self.get(user_id, guild_id) is not None
            if exists:
                return True

        await self.bot.db.guilds.create(guild_id)

        try:
            await self.bot.db.execute(
                """INSERT INTO members (user_id, guild_id)
                VALUES ($1, $2)""",
                user_id,
                guild_id,
            )
        except asyncpg.exceptions.UniqueViolationError:
            return True
        return False