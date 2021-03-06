import asyncpg

from app import errors


class Messages:
    def __init__(self, db) -> None:
        self.db = db

    async def get(self, message_id: int) -> dict:
        return await self.db.fetchrow(
            """SELECT * FROM messages
            WHERE id=$1""",
            message_id,
        )

    async def create(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        author_id: int,
        is_nsfw: bool,
        check_first: bool = True,
    ) -> bool:
        if check_first:
            exists = await self.get(message_id) is not None
            if exists:
                return True

        is_starboard_message = (
            await self.db.sb_messages.get(message_id) is not None
        )
        if is_starboard_message:
            raise errors.AlreadyStarboardMessage(
                f"Could not create message {message_id} "
                "because it is already starboard message."
            )

        await self.db.guilds.create(guild_id)

        try:
            await self.db.execute(
                """INSERT INTO messages
                (id, guild_id, channel_id, author_id, is_nsfw)
                VALUES ($1, $2, $3, $4, $5)""",
                message_id,
                guild_id,
                channel_id,
                author_id,
                is_nsfw,
            )
        except asyncpg.exceptions.UniqueViolationError:
            return True
        return False
