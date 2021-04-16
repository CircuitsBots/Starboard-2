from typing import Optional, Union

import discord
from discord.ext import commands

from app.i18n import t_

from ... import converters, errors, menus, utils
from ...classes.bot import Bot


class Starboard(commands.Cog):
    "Manage starboards"

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.group(
        name="starboards",
        aliases=["s"],
        brief="List starboards",
        invoke_without_command=True,
    )
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def starboards(
        self, ctx: commands.Context, starboard: converters.Starboard = None
    ) -> None:
        """Lists all starboards, and shows the important
        settings. All settings can be viewed by running
        sb!starboards <starboard>"""
        p = utils.escmd(ctx.prefix)
        if starboard is None:
            starboards = await self.bot.db.starboards.get_many(ctx.guild.id)
            if len(starboards) == 0:
                await ctx.send(
                    t_(
                        "You do not have any starboards. "
                        "Add starboards with `{0}s add "
                        "#channel`."
                    ).format(p)
                )
                return

            embed = discord.Embed(
                title=t_("Starboards for **{0}**:").format(ctx.guild),
                description=t_(
                    "This lists the starboards and their "
                    "most important settings. To view all "
                    "settings, run `{0}starboards #starboard`."
                ).format(p),
                color=self.bot.theme_color,
            )
            for s in starboards:
                c = ctx.guild.get_channel(s["id"])
                emoji_str = utils.pretty_emoji_string(
                    s["star_emojis"], ctx.guild
                )
                embed.add_field(
                    name=c.name
                    if c
                    else t_("Deleted Channel {0}").format(s["id"]),
                    value=(
                        f"emojis: **{emoji_str}**\n"
                        f"requiredStars: **{s['required']}**\n"
                    ),
                )
            await ctx.send(embed=embed)
        else:
            s = starboard.sql
            upvote_emoji_str = utils.pretty_emoji_string(
                s["star_emojis"], ctx.guild
            )
            embed = discord.Embed(
                title=starboard.obj.name,
                description=(
                    f"emojis: **{upvote_emoji_str}**\n"
                    f"displayEmoji: **{s['display_emoji']}**\n"
                    f"color: **{s['color']}**\n"
                    f"useWebhook: **{s['use_webhook']}**\n"
                    f"username: **{s['webhook_name']}**\n"
                    + (
                        f"avatar: [view]({s['webhook_avatar']})\n"
                        if s["webhook_avatar"]
                        else "avatar: Default\n"
                    )
                    + "\n"
                    f"requiredStars: **{s['required']}**\n"
                    f"requiredRemove: **{s['required_remove']}**\n"
                    f"selfStar: **{s['self_star']}**\n"
                    f"allowBots: **{s['allow_bots']}**\n"
                    f"imagesOnly: **{s['images_only']}**\n"
                    f"regex: `{s['regex'] or 'None'}`\n"
                    f"excludeRegex: `{s['exclude_regex'] or 'None'}`\n"
                    "\n"
                    f"ping: **{s['ping']}**\n"
                    f"autoReact: **{s['autoreact']}**\n"
                    f"linkDeletes: **{s['link_deletes']}**\n"
                    f"linkEdits: **{s['link_edits']}**\n"
                    f"noXp: **{s['no_xp']}**\n"
                    f"allowRandom: **{s['explore']}**\n"
                ),
                color=self.bot.theme_color,
            )
            await ctx.send(embed=embed)

    @starboards.command(
        name="webhook",
        aliases=["useWebhook"],
        brief="Whether or not to use webhooks for starboard messages.",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def use_webhook(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        enable: converters.mybool,
    ):
        """Whether or not to use webhooks for starboard messages."""
        await self.bot.db.starboards.edit(
            starboard_id=starboard.obj.id, use_webhook=enable
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"useWebhook": (starboard.sql["use_webhook"], enable)},
                bot=self.bot,
            )
        )

    @starboards.command(
        name="avatar", brief="Sets the avatar for webhook starboard messages."
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.guild_only()
    async def set_webhook_avatar(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        avatar_url: Optional[str] = None,
    ):
        """Sets the avatar for webhook starboard messages."""
        if not starboard.sql["use_webhook"] and await menus.Confirm(
            t_(
                "This feature only works if `useWebhook` is enabled. "
                "Would you like to also enable this setting?"
            )
        ).start(ctx):
            await self.bot.db.starboards.edit(
                starboard.obj.id, use_webhook=True
            )
            await ctx.send(
                t_("Webhooks have been enabled for {0}.").format(
                    starboard.obj.mention
                )
            )
        await self.bot.db.starboards.set_webhook_avatar(
            starboard.obj.id, avatar_url
        )

        if avatar_url:
            await ctx.send(t_("Avatar set!"))
        else:
            await ctx.send(t_("Avatar reset to default."))

    @starboards.command(
        name="name",
        aliases=["username"],
        brief="Sets the username for webhook starboard messages.",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_webhook_name(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        *,
        name: Optional[str] = None,
    ):
        """Sets the username for webhook starboard messages"""
        enabled = False
        if not starboard.sql["use_webhook"] and await menus.Confirm(
            t_(
                "This feature only works if `useWebhook` is enabled. "
                "Would you like to also enable this setting?"
            )
        ).start(ctx):
            await self.bot.db.starboards.edit(
                starboard.obj.id, use_webhook=True
            )
            enabled = True
        await self.bot.db.starboards.set_webhook_name(starboard.obj.id, name)

        settings = {"webhookName": (starboard.sql["webhook_name"], name)}
        if enabled:
            settings["useWebhook"] = (False, True)

        await ctx.send(
            embed=utils.cs_embed(
                settings,
                self.bot,
            )
        )

    @starboards.command(name="add", aliases=["a"], brief="Adds a starboard")
    @commands.has_guild_permissions(manage_channels=True)
    async def add_starboard(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Adds a starboard"""
        existed = await self.bot.db.starboards.create(channel.id, ctx.guild.id)
        if existed:
            raise errors.AlreadyStarboard(channel.mention)
        else:
            await ctx.send(
                t_("Created starboard {0}.").format(channel.mention)
            )

    @starboards.command(
        name="remove",
        aliases=["delete", "del", "r"],
        brief="Removes a starboard",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(
        add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def remove_starboard(
        self, ctx: commands.Context, channel: Union[discord.TextChannel, int]
    ) -> None:
        """Deletes a starboard. Will not actually
        delete the channel, or the messages in the
        channel. This action is irreversable."""
        cid = channel.id if type(channel) is not int else channel
        cname = channel.mention if type(channel) is not int else channel
        starboard = await self.bot.db.starboards.get(cid)
        if not starboard:
            raise errors.NotStarboard(cname)
        else:
            confirmed = await menus.Confirm(
                t_("Are you sure? All starboard messages will be lost.")
            ).start(ctx)
            if confirmed is True:
                await self.bot.db.starboards.delete(cid)
                await ctx.send(
                    t_("{0} is no longer a starboard.").format(cname)
                )
            if confirmed is False:
                await ctx.send(t_("Cancelled."))

    @starboards.command(
        name="displayEmoji",
        aliases=["de"],
        brief="Set the emoji to show next to the points",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_display_emoji(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        emoji: converters.Emoji,
    ) -> None:
        """Sets the emoji that is shown next to the points
        on starboard messages"""
        clean = utils.clean_emoji(emoji)
        await self.bot.db.starboards.edit(
            starboard.obj.id, display_emoji=clean
        )
        orig = utils.pretty_emoji_string(
            starboard.sql["display_emoji"], ctx.guild
        )
        await ctx.send(
            embed=utils.cs_embed({"displayEmoji": (orig, emoji)}, self.bot)
        )

    @starboards.command(
        name="color",
        aliases=["colour"],
        brief="Sets the embed color of starboard messages",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_color(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        *,
        color: Optional[commands.ColorConverter],
    ) -> None:
        """Sets the embed color of starboard messages for a
        specific starboard"""
        color = (
            str(color)
            if color
            else hex(self.bot.theme_color).replace("0x", "#")
        )

        await self.bot.db.starboards.edit(starboard.obj.id, color=color)
        await ctx.send(
            embed=utils.cs_embed(
                {"color": (starboard.sql["color"], color)}, self.bot
            )
        )

    @starboards.command(
        name="required",
        aliases=["requiredStars", "requiredPoints"],
        brief="Sets the number of reactions a message needs",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_required(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        required: converters.myint,
    ) -> None:
        """How many points a message needs for it to appear on the
        starboard"""
        await self.bot.db.starboards.edit(starboard.obj.id, required=required)
        await ctx.send(
            embed=utils.cs_embed(
                {"required": (starboard.sql["required"], required)}, self.bot
            )
        )

    @starboards.command(
        name="requiredRemove",
        aliases=["rtm"],
        brief="How few stars a message has before it is removed",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_required_remove(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        required_remove: converters.myint,
    ) -> None:
        """If a message is on the starboard and then it looses
        stars (or whatever the emoji is), this determines at what
        point the message will be removed from the starboard."""
        await self.bot.db.starboards.edit(
            starboard.obj.id, required_remove=required_remove
        )
        await ctx.send(
            embed=utils.cs_embed(
                {
                    "requiredRemove": (
                        starboard.sql["required_remove"],
                        required_remove,
                    )
                },
                self.bot,
            )
        )

    @starboards.command(
        name="selfStar",
        aliases=["ss"],
        brief="Whether or not users can star their own messages",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_self_star(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        self_star: converters.mybool,
    ) -> None:
        """Whether or not to allow users to star their own messages"""
        await self.bot.db.starboards.edit(
            starboard.obj.id, self_star=self_star
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"selfStar": (starboard.sql["self_star"], self_star)}, self.bot
            )
        )

    @starboards.command(
        name="allowBots",
        aliases=["ab"],
        brief="Whether or not bot messages can appear on the starboard",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_allow_Bots(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        allow_bots: converters.mybool,
    ) -> None:
        """Whether or not to allow bot messages to appear on the starboard"""
        await self.bot.db.starboards.edit(
            starboard.obj.id, allow_bots=allow_bots
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"allowBots": (starboard.sql["allow_bots"], allow_bots)},
                self.bot,
            )
        )

    @starboards.command(
        name="imagesOnly",
        aliases=["requireImage", "io"],
        brief="Whether messages must include an image",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_images_only(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        images_only: converters.mybool,
    ) -> None:
        """Whether messages must include an image in order to appear
        on the starboard"""
        await self.bot.db.starboards.edit(
            starboard.obj.id, images_only=images_only
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"imagesOnly": (starboard.sql["images_only"], images_only)},
                self.bot,
            )
        )

    @starboards.command(
        name="regex",
        aliases=["reg"],
        brief="A regex string that all messages must match",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_regex(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        regex: Optional[str] = None,
    ) -> None:
        """A regex string that the content of starboard messages must match.
        If the regex string takes too long to match, Starboard will assume
        that it matched and send a warning to your logChannel."""
        await self.bot.db.starboards.edit(starboard.obj.id, regex=regex)
        await ctx.send(
            embed=utils.cs_embed(
                {"regex": (starboard.sql["regex"], regex)}, self.bot
            )
        )

    @starboards.command(
        name="excludeRegex",
        aliases=["eregex", "ereg"],
        brief="A regex string that all messages must not match",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_eregex(
        self,
        ctx: commands.context,
        starboard: converters.Starboard,
        exclude_regex: Optional[str] = None,
    ) -> None:
        """A regex string that the content of starboard messages must NOT
        match."""
        await self.bot.db.starboards.edit(
            starboard.obj.id, exclude_regex=exclude_regex
        )
        await ctx.send(
            embed=utils.cs_embed(
                {
                    "excludeRegex": (
                        starboard.sql["exclude_regex"],
                        exclude_regex,
                    )
                },
                self.bot,
            )
        )

    @starboards.command(
        name="ping",
        aliases=["mentionAuthor"],
        brief="Whether or not to mention the author of a starboard message",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_ping(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        ping: converters.mybool,
    ) -> None:
        """Whether or not to mention the author of messages if the message
        appears on a starboard."""
        await self.bot.db.starboards.edit(starboard.obj.id, ping=ping)
        await ctx.send(
            embed=utils.cs_embed(
                {"ping": (starboard.sql["ping"], ping)}, self.bot
            )
        )

    @starboards.command(
        name="autoReact",
        aliases=["ar"],
        brief="Whether to automatically react to starboard messages",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_auto_react(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        auto_react: converters.mybool,
    ) -> None:
        """Whether or not to automatically react to starboard messages."""
        await self.bot.db.starboards.edit(
            starboard.obj.id, autoreact=auto_react
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"autoReact": (starboard.sql["autoreact"], auto_react)},
                self.bot,
            )
        )

    @starboards.command(
        name="linkDeletes",
        aliases=["ld"],
        brief="Whether to delete the starboard message if the original is",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_link_deletes(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        link_deletes: converters.mybool,
    ) -> None:
        """If the original message is deleted and this is set to true, then
        the starboard message will also be deleted."""
        await self.bot.db.starboards.edit(
            starboard.obj.id, link_deletes=link_deletes
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"linkDeletes": (starboard.sql["link_deletes"], link_deletes)},
                self.bot,
            )
        )

    @starboards.command(
        name="linkEdits",
        aliases=["le"],
        brief="Whether to update starboard messages with edited content",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_link_edits(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        link_edits: converters.mybool,
    ) -> None:
        """If this is set to false, once a message appears on the starboard
        the content of the message will not update."""
        await self.bot.db.starboards.edit(
            starboard.obj.id, link_edits=link_edits
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"linkEdits": (starboard.sql["link_edits"], link_edits)},
                self.bot,
            )
        )

    @starboards.command(
        name="noXp",
        brief="Set to True to disable gaining XP for this starboard",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_no_xp(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        no_xp: converters.mybool,
    ) -> None:
        """If set to true, then the starEmojis for this starboard will
        not count as XP for the user that received them."""
        await self.bot.db.starboards.edit(starboard.obj.id, no_xp=no_xp)
        await ctx.send(
            embed=utils.cs_embed(
                {"noXp": (starboard.sql["no_xp"], no_xp)}, self.bot
            )
        )

    @starboards.command(
        name="allowRandom",
        aliases=["rand", "explore"],
        brief="Whether or not the random command can pull from this starboard",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_allow_random(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        allow_random: converters.mybool,
    ) -> None:
        """Whether or not the random command can pull messages from this
        starboard"""
        await self.bot.db.starboards.edit(
            starboard.obj.id, explore=allow_random
        )
        await ctx.send(
            embed=utils.cs_embed(
                {"allowRandom": (starboard.sql["explore"], allow_random)},
                self.bot,
            )
        )

    @starboards.group(
        name="starEmojis",
        aliases=["emojis", "se", "e"],
        brief="Modify starEmojis for a starboard",
        invoke_without_command=True,
    )
    @commands.has_guild_permissions(manage_channels=True)
    async def star_emojis(self, ctx: commands.Context) -> None:
        """Modify the star emojis for a starboard"""
        await ctx.send_help(ctx.command)

    @star_emojis.command(
        name="set", brief="Sets the starEmojis for a starboard"
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def set_star_emojis(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        *emojis: converters.Emoji,
    ) -> None:
        """Accepts a list of emojis to replace the old starEmojis
        on a starboard."""
        converted_emojis = [utils.clean_emoji(e) for e in emojis]
        original_emojis = starboard.sql["star_emojis"]

        await self.bot.db.starboards.edit(
            starboard.obj.id, star_emojis=converted_emojis
        )

        pretty_orig_emojis = utils.pretty_emoji_string(
            original_emojis, ctx.guild
        )
        pretty_new_emojis = utils.pretty_emoji_string(
            converted_emojis, ctx.guild
        )

        await ctx.send(
            embed=utils.cs_embed(
                {"starEmojis": (pretty_orig_emojis, pretty_new_emojis)},
                self.bot,
                noticks=True,
            )
        )

    @star_emojis.command(name="add", aliases=["a"], brief="Add a starEmoji")
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def add_star_emoji(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        emoji: converters.Emoji,
    ) -> None:
        """Adds a starEmoji to a starboard"""
        converted_emoji = utils.clean_emoji(emoji)

        current_emojis = starboard.sql["star_emojis"]

        if converted_emoji in current_emojis:
            raise errors.AlreadySBEmoji(emoji, starboard.obj.mention)

        new_emojis = current_emojis + [converted_emoji]

        await self.bot.db.starboards.add_star_emoji(
            starboard.obj.id, emoji=converted_emoji
        )

        pretty_orig_emojis = utils.pretty_emoji_string(
            current_emojis, ctx.guild
        )
        pretty_new_emojis = utils.pretty_emoji_string(new_emojis, ctx.guild)

        await ctx.send(
            embed=utils.cs_embed(
                {"starEmojis": (pretty_orig_emojis, pretty_new_emojis)},
                self.bot,
                noticks=True,
            )
        )

    @star_emojis.command(
        name="remove", aliases=["r", "del"], brief="Removes a starEmoji"
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def remove_star_emoji(
        self,
        ctx: commands.Context,
        starboard: converters.Starboard,
        emoji: converters.Emoji,
    ) -> None:
        """Removes a starEmoji from a starboard"""
        converted_emoji = utils.clean_emoji(emoji)

        current_emojis = starboard.sql["star_emojis"]

        if converted_emoji not in current_emojis:
            raise errors.NotSBEmoji(emoji, starboard.obj.mention)

        new_emojis = current_emojis.copy()
        new_emojis.remove(converted_emoji)

        await self.bot.db.starboards.remove_star_emoji(
            starboard.obj.id, emoji=converted_emoji
        )

        pretty_orig_emojis = utils.pretty_emoji_string(
            current_emojis, ctx.guild
        )
        pretty_new_emojis = utils.pretty_emoji_string(new_emojis, ctx.guild)

        await ctx.send(
            embed=utils.cs_embed(
                {"starEmojis": (pretty_orig_emojis, pretty_new_emojis)},
                self.bot,
                noticks=True,
            )
        )

    @star_emojis.command(
        name="clear",
        aliases=["removeAll"],
        brief="Clears all starEmojis for a starboard",
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(
        embed_links=True, add_reactions=True, read_message_history=True
    )
    @commands.guild_only()
    async def clear_star_emojis(
        self, ctx: commands.Context, starboard: converters.Starboard
    ) -> None:
        """Removes all starEmojis from a starboard"""
        if not await menus.Confirm(
            t_("Are you sure you want to clear all emojis for {0}?").format(
                starboard.obj.mention
            )
        ).start(ctx):
            await ctx.send("Cancelled")
            return

        await self.bot.db.starboards.edit(starboard.obj.id, star_emojis=[])

        pretty_orig_emojis = utils.pretty_emoji_string(
            starboard.sql["star_emojis"], ctx.guild
        )
        pretty_new_emoijs = utils.pretty_emoji_string([], ctx.guild)

        await ctx.send(
            embed=utils.cs_embed(
                {"starEmojis": (pretty_orig_emojis, pretty_new_emoijs)},
                self.bot,
                noticks=True,
            )
        )


def setup(bot: Bot) -> None:
    bot.add_cog(Starboard(bot))
