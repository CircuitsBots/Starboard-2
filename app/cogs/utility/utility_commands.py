import asyncio

import discord
from discord.ext import commands, flags

from app import converters, errors, menus, utils
from app.classes.bot import Bot
from app.cogs.leveling import leveling_funcs
from app.cogs.starboard import starboard_funcs
from app.i18n import t_

from . import cleaner, debugger, recounter, utility_funcs


class Utility(commands.Cog):
    "Utility and starboard moderation"

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.group(
        name="reset",
        brief="A utility for resetting aspects of the bot.",
        invoke_without_command=True,
    )
    @commands.has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def reset(self, ctx: commands.Context):
        "A utility for resetting aspects of the bot."
        await ctx.send_help(ctx.command)

    @reset.command(name="all", brief="Resets the bot for your guild.")
    @commands.has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def reset_all(self, ctx: commands.Context):
        """Resets Starboard on the entire guild. All settings,
        starboards, autostarchannels, and leaderboard data will be
        lost permanently."""
        await ctx.send(
            "You are about to reset all settings, starboards, "
            "autostarchannels, and leaderboard data for this "
            "server. Please type the name of this server to "
            "continue, or anything else to cancel."
        )

        def check(m: discord.Message) -> bool:
            if m.author.id != ctx.author.id:
                return False
            if m.channel.id != ctx.channel.id:
                return False
            return True

        try:
            m = await self.bot.wait_for("message", check=check)
        except asyncio.TimeoutError:
            await ctx.send(t_("Cancelled."))
            return
        if m.content.casefold() != ctx.guild.name.casefold():
            await ctx.send(t_("Cancelled."))
            return

        if not await menus.Confirm(t_("Are you certain?")).start(ctx):
            await ctx.send(t_("Cancelled."))
            return

        await self.bot.db.guilds.delete(ctx.guild.id)
        await ctx.send(t_("Starboard has been reset for this server."))

    @reset.command(
        name="leaderboard", aliases=["lb"], brief="Resets the leaderboard."
    )
    @commands.has_guild_permissions(manage_guild=True)
    @commands.guild_only()
    async def reset_lb(self, ctx: commands.Context):
        """Resets only the leaderboard for a guild"""
        if not await menus.Confirm(t_("Reset the leaderboard?")).start(ctx):
            await ctx.send(t_("Cancelled."))
            return
        await self.bot.db.execute(
            """UPDATE members
            SET xp=0,
            level=0
            WHERE guild_id=$1""",
            ctx.guild.id,
        )
        await ctx.send(t_("Reset the leaderboard."))

    @commands.command(name="setxp", brief="Sets the XP for a user.")
    @commands.has_guild_permissions(manage_guild=True)
    async def set_user_xp(
        self, ctx: commands.Context, user: discord.User, xp: converters.myint
    ):
        """Sets the XP for a user. The level will be calculated
        automatically"""
        if xp < 0:
            raise commands.BadArgument(t_("XP must be greater than 0."))
        if xp > 9999:
            raise commands.BadArgument(t_("XP must be less than 10,000."))

        sql_member = await self.bot.db.members.get(user.id, ctx.guild.id)
        if not sql_member:
            raise commands.BadArgument(
                t_("That user does not exist in the database for this guild.")
            )

        new_level = leveling_funcs.current_level(xp)
        await self.bot.db.execute(
            """UPDATE members
            SET xp=$1,
            level=$2
            WHERE user_id=$3
            AND guild_id=$4""",
            xp,
            new_level,
            user.id,
            ctx.guild.id,
        )

        await ctx.send(
            t_(
                "Changed {0}'s XP to {1} and Level to {2} "
                "(was {3} XP and Level {4})."
            ).format(
                user.name, xp, new_level, sql_member["xp"], sql_member["level"]
            )
        )

    @commands.command(
        name="scan", brief="Recounts the reactions on lots of messages at once"
    )
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_permissions(read_message_history=True)
    @commands.guild_only()
    async def scan_recount(self, ctx: commands.Context, limit: int) -> None:
        """Helpful if several messages were starred during downtime. Running
        this will scan up to the last 1,000 messages and recount the reactions
        on them."""
        if limit < 1:
            await ctx.send(t_("Must recount at least 1 message."))
            return
        if limit > 1000:
            await ctx.send(t_("Can only recount up to 1,000 messages."))
            return
        async with ctx.typing():
            await recounter.scan_recount(self.bot, ctx.channel, limit)
        await ctx.send("Finished!")

    @commands.command(
        name="recount",
        aliases=["refresh"],
        brief="Recounts the reactions on a message",
    )
    @commands.cooldown(3, 6, type=commands.BucketType.guild)
    @commands.has_guild_permissions(manage_messages=True)
    async def recount(
        self, ctx: commands.Context, message: converters.GuildMessage
    ) -> None:
        """Recounts the reactions on a specific message"""
        orig_sql_message = await starboard_funcs.orig_message(
            self.bot, message.id
        )
        if not orig_sql_message:
            await self.bot.db.messages.create(
                message.id,
                ctx.guild.id,
                ctx.channel.id,
                ctx.author.id,
                ctx.channel.is_nsfw(),
            )
        else:
            message = await self.bot.cache.fetch_message(
                ctx.guild.id,
                int(orig_sql_message["channel_id"]),
                int(orig_sql_message["id"]),
            )
        async with ctx.typing():
            await recounter.recount_reactions(self.bot, message)
        await ctx.send("Finished!")

    @commands.command(
        name="clean",
        brief="Cleans things like #deleted-channel and @deleted-role",
    )
    @commands.cooldown(1, 5, type=commands.BucketType.guild)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def clean(self, ctx: commands.Context) -> None:
        """Removes thing such as #deleted-channel and @deleted-role
        from the database. Note that this can actually change
        the functionality of things like permroles and blacklists."""
        result = await cleaner.clean_guild(ctx.guild, self.bot)
        string = "\n".join(
            f"{name}: {count}" for name, count in result if count != 0
        )
        if string == "":
            string = t_("Nothing to remove")
        embed = discord.Embed(
            title=t_("Database Cleaning"),
            description=string,
            color=self.bot.theme_color,
        )
        await ctx.send(embed=embed)

    @commands.command(
        name="debug", brief="Looks for problems with your current setup"
    )
    @commands.cooldown(2, 5, type=commands.BucketType.guild)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_permissions(
        embed_links=True, add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def debug(self, ctx: commands.Context) -> None:
        """Tries to determine any problems with the current setup
        of Starboard."""
        result = await debugger.debug_guild(self.bot, ctx.guild)

        p = commands.Paginator(prefix="", suffix="")

        p.add_line(
            t_(
                "{0} errors, {1} warnings, {2} notes, and {3} suggestions."
            ).format(
                len(result["errors"]),
                len(result["warns"]),
                len(result["light_warns"]),
                len(result["suggestions"]),
            )
        )
        if result["errors"]:
            p.add_line(t_("\n\n**Errors:**"))
            for e in result["errors"]:
                p.add_line(f"\n{e}")
        if result["warns"]:
            p.add_line(t_("\n\n**Warnings:**"))
            for e in result["warns"]:
                p.add_line(f"\n{e}")
        if result["light_warns"]:
            p.add_line(t_("\n\n**Notes:**"))
            for e in result["light_warns"]:
                p.add_line(f"\n{e}")
        if result["suggestions"]:
            p.add_line(t_("\n\n**Suggestions:**"))
            for e in result["suggestions"]:
                p.add_line(f"\n{e}")

        embeds = [
            discord.Embed(
                title=t_("Debugging Results"),
                description=page,
                color=self.bot.theme_color,
            )
            for page in p.pages
        ]
        await menus.Paginator(embeds=embeds, delete_after=True).start(ctx)

    @commands.command(name="freeze", brief="Freeze a message")
    @commands.has_guild_permissions(manage_messages=True)
    async def freeze_message(
        self, ctx: commands.Context, message_link: converters.GuildMessage
    ) -> None:
        """Freezes a message, so the point count will
        not update."""
        orig_message = await starboard_funcs.orig_message(
            self.bot, message_link.id
        )
        if not orig_message:
            raise errors.MessageNotInDatabse()
        await utility_funcs.handle_freezing(
            self.bot, orig_message["id"], orig_message["guild_id"], True
        )
        await ctx.send("Message frozen.")

    @commands.command(name="unfreeze", brief="Unfreezes a message")
    @commands.has_guild_permissions(manage_messages=True)
    async def unfreeze_message(
        self, ctx: commands.Context, message_link: converters.GuildMessage
    ) -> None:
        """Unfreezes a message"""
        orig_message = await starboard_funcs.orig_message(
            self.bot, message_link.id
        )
        if not orig_message:
            raise errors.MessageNotInDatabse()
        await utility_funcs.handle_freezing(
            self.bot, orig_message["id"], orig_message["guild_id"], False
        )
        await ctx.send(t_("Message unfrozen."))

    @commands.command(
        name="force", brief="Forced a message to certain starboards"
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(
        add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def force_message(
        self,
        ctx: commands.Context,
        message_link: converters.GuildMessage,
        *starboards: converters.Starboard,
    ) -> None:
        """Forces a message to all or some starboards.

        A forced message will appear on the starboard,
        event if the channel is blacklisted, the
        message author is blacklisted, or the number of
        reaction on the message is less than the starboards
        required setting.

        Usage:
            force <message link> [starboard1, starboard2, ...]
        Examples:
            force <message link> #starboard #super-starboard
            force <message link> #super-starboard
            force <message link>
        """
        starboards = [int(s.sql["id"]) for s in starboards]
        if len(starboards) == 0:
            if not await menus.Confirm(
                t_("Force this message to all starboards?")
            ).start(ctx):
                await ctx.send(t_("Cancelled."))
                return
        orig_sql_message = await starboard_funcs.orig_message(
            self.bot, message_link.id
        )
        if orig_sql_message is None:
            await self.bot.db.users.create(
                message_link.author.id, message_link.author.bot
            )
            await self.bot.db.messages.create(
                message_link.id,
                message_link.guild.id,
                message_link.channel.id,
                message_link.author.id,
                message_link.channel.is_nsfw(),
            )
            orig_sql_message = await self.bot.db.messages.get(message_link.id)

        await utility_funcs.handle_forcing(
            self.bot,
            orig_sql_message["id"],
            orig_sql_message["guild_id"],
            starboards,
            True,
        )
        if len(starboards) == 0:
            await ctx.send(t_("Message forced to all starboards."))
        else:
            converted = [f"<#{s}>" for s in starboards]
            await ctx.send(
                t_("Message forced to {0}.").format(", ".join(converted))
            )

    @commands.command(
        name="unforce", brief="Unforces a message from certain starboards"
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(
        add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def unforce_message(
        self,
        ctx: commands.Context,
        message_link: converters.GuildMessage,
        *starboards: converters.Starboard,
    ) -> None:
        """Unforces a message

        Usage:
            unforce <message link> [starboard1, starboard2, ...]
        Examples:
            unforce <message link> #starboard #super-starboard
            unforce <message link> #super-starboard
            unforce <message link>"""
        starboards = [int(s.sql["id"]) for s in starboards]

        orig_sql_message = await starboard_funcs.orig_message(
            self.bot, message_link.id
        )
        if not orig_sql_message:
            raise errors.MessageNotInDatabse()
        if orig_sql_message["id"] != message_link.id and len(starboards) == 0:
            if await menus.Confirm(
                t_(
                    "The message you passed appears to be a starboard "
                    "message. Would you like to unforce this message "
                    "from {0} instead?"
                ).format(message_link.channel.mention)
            ).start(ctx):
                starboards = [message_link.channel.id]

        if len(starboards) == 0:
            if not await menus.Confirm(
                t_("Unforce this message from all starboards?")
            ).start(ctx):
                await ctx.send(t_("Cancelled."))
                return
        await utility_funcs.handle_forcing(
            self.bot,
            orig_sql_message["id"],
            orig_sql_message["guild_id"],
            starboards,
            False,
        )
        if len(starboards) == 0:
            await ctx.send(t_("Message unforced from all starboards."))
        else:
            converted = [f"<#{s}>" for s in starboards]
            await ctx.send(
                t_("Message unforced from {0}.").format(", ".join(converted))
            )

    @commands.command(
        name="trashreason",
        aliases=["reason"],
        brief="Sets the reason for trashing a message",
    )
    @commands.has_guild_permissions(manage_messages=True)
    async def set_trash_reason(
        self,
        ctx: commands.Context,
        message: converters.GuildMessage,
        *,
        reason: str = None,
    ) -> None:
        """Sets the reason for trashing a message."""
        orig_message = await starboard_funcs.orig_message(self.bot, message.id)
        if not orig_message:
            raise errors.MessageNotInDatabse()
        await utility_funcs.set_trash_reason(
            self.bot, orig_message["id"], ctx.guild.id, reason or "None given"
        )
        await ctx.send(t_("Set the reason to {0}.").format(reason))

    @commands.command(
        name="trash", brief="Trashes a message so it can't be viewed"
    )
    @commands.has_guild_permissions(manage_messages=True)
    async def trash_message(
        self,
        ctx: commands.Context,
        message_link: converters.GuildMessage,
        *,
        reason=None,
    ) -> None:
        """Trashes a message for all starboards.

        A trashed message cannot be starred, added to
        more starboards, or be viewed on any of the
        current starboards."""
        orig_sql_message = await starboard_funcs.orig_message(
            self.bot, message_link.id
        )
        if not orig_sql_message:
            raise errors.MessageNotInDatabse()
        await utility_funcs.handle_trashing(
            self.bot,
            orig_sql_message["id"],
            orig_sql_message["guild_id"],
            True,
            reason or "No reason given",
        )
        await ctx.send(t_("Message trashed."))

    @commands.command(name="untrash", brief="Untrashes a message")
    @commands.has_guild_permissions(manage_messages=True)
    async def untrash_message(
        self, ctx: commands.Context, message_link: discord.PartialMessage
    ) -> None:
        """Untrashes a message for all starboards"""
        orig_sql_message = await starboard_funcs.orig_message(
            self.bot, message_link.id
        )
        if not orig_sql_message:
            raise errors.MessageNotInDatabse()
        await utility_funcs.handle_trashing(
            self.bot,
            orig_sql_message["id"],
            orig_sql_message["guild_id"],
            False,
        )
        await ctx.send(t_("Message untrashed."))

    @commands.group(
        name="trashcan",
        aliases=["trashed"],
        brief="Shows a list of trashed messages",
        invoke_without_command=True,
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(
        embed_links=True, add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def trashcan(self, ctx: commands.Context) -> None:
        """Shows all messages that have been trashed."""
        trashed_messages = await self.bot.db.fetch(
            """SELECT * FROM messages
            WHERE guild_id=$1 AND trashed=True""",
            ctx.guild.id,
        )
        if len(trashed_messages) == 0:
            await ctx.send(t_("You have no trashed messages."))
            return
        p = commands.Paginator(prefix="", suffix="", max_size=2000)
        for m in trashed_messages:
            link = utils.jump_link(m["id"], m["channel_id"], m["guild_id"])
            p.add_line(
                f"**[{m['channel_id']}-{m['id']}]({link})**: "
                f"`{utils.escmd(m['trash_reason'])}`"
            )
        embeds = [
            discord.Embed(
                title=t_("Trashed Messages"),
                description=page,
                color=self.bot.theme_color,
            )
            for page in p.pages
        ]
        await menus.Paginator(embeds=embeds).start(ctx)

    @trashcan.command(
        name="empty",
        aliases=["clear"],
        brief="Empties the trashcan",
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(
        embed_links=True, add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def empty_trashcan(self, ctx: commands.Context):
        """Empties the trashcan. Note that this will not
        Automatically update the messages that were trashed.
        If you need this, please untrash each message
        individually."""
        if not await menus.Confirm(
            t_("Are you sure you want to untrash all messages?")
        ).start(ctx):
            await ctx.send("Cancelled.")
        await self.bot.db.execute(
            """UPDATE messages
            SET trashed=False
            WHERE guild_id=$1 and trashed=True""",
            ctx.guild.id,
        )
        await ctx.send(t_("All messages have been untrashed."))

    @flags.add_flag("--by", type=discord.User)
    @flags.add_flag("--notby", type=discord.User)
    @flags.add_flag("--contains", type=str)
    @flags.command(
        name="purge", brief="Trashes a large number of messages at once"
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, embed_links=True)
    @commands.guild_only()
    async def purgetrash(
        self, ctx: commands.Context, limit: converters.myint, **flags
    ) -> None:
        """Works similar to a normal purge command,
        but instead of deleting the messages, each
        message is trashed. See sb!help trash for
        info on trashing.

        Can only trash up to 200 messages at once.

        Usage:
            purge <limit> <options>
        Options:
            --by: Only trash messages by this author
            --notby: Do not trash message by this author
            --contains: Only trash messages that contain
                this phrase.
        Examples:
            trash 50 --by @Circuit
            trash 50 --contains bad-word
            trash 50 --notby @Cool Person
            trash 50"""
        if limit > 200:
            raise commands.BadArgument(
                t_("Can only purge up to 200 messages at once.")
            )
        elif limit < 1:
            raise commands.BadArgument("Must purge at least 1 message.")

        total, purged = await utility_funcs.handle_purging(
            self.bot,
            ctx.channel,
            limit,
            True,
            flags["by"],
            flags["notby"],
            flags["contains"],
        )

        embed = discord.Embed(
            title=t_("Purged {0} Messages.").format(total),
            description="\n".join([f"<@{u}>: {c}" for u, c in purged.items()]),
            color=self.bot.theme_color,
        )

        await ctx.send(embed=embed)

    @flags.add_flag("--by", type=discord.User)
    @flags.add_flag("--notby", type=discord.User)
    @flags.add_flag("--contains", type=str)
    @flags.command(
        name="unpurge", brief="Untrashes a large number of messages at once"
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(read_message_history=True, embed_links=True)
    async def unpurgetrash(
        self, ctx: commands.Context, limit: converters.myint, **flags
    ) -> None:
        """Same usage as purge, but untrashes instead."""
        if limit > 200:
            raise commands.BadArgument(
                t_("Can only unpurge up to 200 messages at once.")
            )
        elif limit < 1:
            raise commands.BadArgument("Must unpurge at least 1 message.")

        total, purged = await utility_funcs.handle_purging(
            self.bot,
            ctx.channel,
            limit,
            False,
            flags["by"],
            flags["notby"],
            flags["contains"],
        )

        embed = discord.Embed(
            title=t_("Unpurged {0} Messages.").format(total),
            description="\n".join([f"<@{u}>: {c}" for u, c in purged.items()]),
            color=self.bot.theme_color,
        )

        await ctx.send(embed=embed)

    @commands.command(
        name="messageInfo",
        aliases=["mi"],
        brief="Shows information on a message",
    )
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def message_info(
        self, ctx: commands.Context, message: converters.GuildMessage
    ) -> None:
        """Shows useful info on a message."""
        orig = await starboard_funcs.orig_message(self.bot, message.id)
        if not orig:
            raise errors.MessageNotInDatabse()
        jump = utils.jump_link(
            orig["id"], orig["channel_id"], orig["guild_id"]
        )
        embed = discord.Embed(
            title=t_("Message Info"),
            color=self.bot.theme_color,
            description=t_(
                "[Jump to Message]({0})\n"
                "Channel: <#{1[channel_id]}>\n"
                "ID: {1[id]} (`{1[channel_id]}-{1[id]}`)\n"
                "Author: <@{1[author_id]}> | `{1[author_id]}`\n"
                "Trashed: {1[trashed]}\n"
                "Frozen: {1[frozen]}"
            ).format(jump, orig),
        )
        for s in await self.bot.db.starboards.get_many(ctx.guild.id):
            s_obj = ctx.guild.get_channel(int(s["id"]))
            if not s_obj:
                continue
            sb_message = await self.bot.db.fetchrow(
                """SELECT * FROM starboard_messages
                WHERE orig_id=$1 AND starboard_id=$2""",
                orig["id"],
                s["id"],
            )
            if not sb_message:
                jump = t_("Not On Starboard")
                points = 0
                forced = False
            else:
                _jump = utils.jump_link(
                    sb_message["id"],
                    sb_message["starboard_id"],
                    orig["guild_id"],
                )
                jump = t_("[Jump]({0})").format(_jump)
                points = sb_message["points"]
                forced = s["id"] in orig["forced"]
            embed.add_field(
                name=s_obj.name,
                value=(
                    f"<#{s['id']}>: {jump}\n"
                    + t_("Points: **{0}**/{1}\nForced: {2}").format(
                        points, s["required"], forced
                    )
                ),
            )

        await ctx.send(embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(Utility(bot))
