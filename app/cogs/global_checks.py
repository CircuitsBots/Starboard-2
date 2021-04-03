from discord.ext import commands

from app import errors
from app.classes.bot import Bot
from app.i18n import t_


async def not_disabled(ctx: commands.Context) -> bool:
    if ctx.guild is None:
        return True
    if ctx.channel.permissions_for(ctx.message.author).manage_guild:
        return True
    guild = await ctx.bot.db.guilds.get(ctx.guild.id)
    if not guild["allow_commands"]:
        raise errors.AllCommandsDisabled()
    name = ctx.command.qualified_name
    if name in guild["disabled_commands"]:
        raise errors.CommandDisabled(
            t_(
                "The command {0} has been disabled "
                "by the moderators of this server."
            ).format(name)
        )
    return True


GLOBAL_CHECKS = [
    not_disabled,
    commands.bot_has_permissions(send_messages=True),
]


def setup(bot: Bot) -> None:
    for check in GLOBAL_CHECKS:
        bot.add_check(check)
