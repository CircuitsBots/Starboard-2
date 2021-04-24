from typing import Optional

import discord
from discord.ext import commands

from app import errors
from app.classes.bot import Bot
from app.i18n import locales, t_


class Profile(commands.Cog):
    """Manage personal settings"""

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command(
        name="language",
        aliases=["lang", "locale"],
        help=t_("Sets your language"),
    )
    async def set_user_language(
        self, ctx: commands.Context, locale: Optional[str]
    ):
        if not locale:
            await ctx.send(
                t_("Valid Language Codes:\n{0}").format("\n".join(locales))
            )
            return
        if locale not in locales:
            raise errors.InvalidLocale(locale)
        await self.bot.db.users.edit(ctx.author.id, locale=locale)
        if ctx.author.id in self.bot.locale_cache:
            self.bot.locale_cache[ctx.author.id] = locale
        await ctx.send(t_("Set your language to {0}.").format(locale))

    @commands.command(
        name="public",
        aliases=["visible"],
        help=t_("Whether or not your profile is visible to others."),
    )
    async def set_user_public(self, ctx: commands.Context, public: bool):
        await self.bot.db.users.edit(ctx.author.id, public=public)
        if public:
            await ctx.send(t_("Your profile is now public."))
        else:
            await ctx.send(t_("Your profile is no longer public."))

    @commands.command(
        name="profile",
        aliases=["me"],
        help=t_("Shows your settings."),
    )
    @commands.cooldown(1, 3, type=commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True)
    async def profile(self, ctx: commands.Context):
        sql_user = await self.bot.db.users.get(ctx.author.id)

        total = sql_user["donation_total"] + sql_user["last_patreon_total"]
        patron = (
            f"Patreon: {sql_user['patron_status']} "
            f"${sql_user['last_known_monthly']}/month "
            f"(${sql_user['last_patreon_total']})"
        )

        embed = (
            discord.Embed(title=str(ctx.author), color=self.bot.theme_color)
            .add_field(
                name=t_("Settings"),
                value=t_("Language: {0}\n" "Public Profile: {1}").format(
                    sql_user["locale"], sql_user["public"]
                ),
                inline=False,
            )
            .add_field(
                name=t_("Premium Info"),
                value=(
                    f"Credits: {sql_user['credits']}\n"
                    f"Patron: {patron}\n"
                    f"Donations: ${sql_user['donation_total']}\n"
                    f"Total Support: ${total}\n"
                ),
            )
        )

        await ctx.send(embed=embed)


def setup(bot: Bot):
    bot.add_cog(Profile(bot))
