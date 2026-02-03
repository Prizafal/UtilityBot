# cogs/bulk_perm_change.py
import os
import io
import csv
import asyncio
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def permCheck(interaction: discord.Interaction) -> bool:
    # Dev or server admin
    if interaction.user and interaction.user.id == DEV_ID:
        return True
    if interaction.guild and isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False


class BulkPermChange(commands.Cog):
    """
    /bulkpermchange action:<Grant/Deny> target:<Role/User> permission:<flag>
    Applies a permission overwrite across **all channels** for the target.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="bulkpermchange",
        description="Grant or deny a permission for a role/user across ALL channels."
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Grant (allow)", value="allow"),
            app_commands.Choice(name="Deny (remove/deny)", value="deny"),
        ]
    )
    @app_commands.describe(
        action="Grant = set overwrite to True, Deny = set overwrite to False",
        target="Role or user to modify",
        permission="Permission flag (e.g. view_channel, send_messages, connect, speak...)"
    )
    @app_commands.check(permCheck)
    @app_commands.guild_only()
    async def bulkpermchange(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        target: Union[discord.Role, discord.Member],
        permission: str,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("Use this in a server.", ephemeral=True)

        me: discord.Member = guild.me
        if not me.guild_permissions.manage_channels:
            return await interaction.followup.send("❌ I need **Manage Channels** permission.", ephemeral=True)

        # Validate permission name
        valid_flags = discord.Permissions.VALID_FLAGS  # dict[str, int]
        if permission not in valid_flags:
            examples = "`view_channel`, `send_messages`, `read_message_history`, `connect`, `speak`"
            return await interaction.followup.send(
                f"❌ `{permission}` is not a valid permission flag.\nTry: {examples}",
                ephemeral=True,
            )

        # Map action -> boolean overwrite value
        value = True if action.value == "allow" else False

        # Iterate channels
        rows = []
        success = failed = 0

        for ch in guild.channels:
            try:
                ow = ch.overwrites_for(target)
                setattr(ow, permission, value)  # True = allow, False = deny
                await ch.set_permissions(
                    target,
                    overwrite=ow,
                    reason=f"Bulk perm change by {interaction.user} ({permission}={value})"
                )
                success += 1
                rows.append((ch.name, ch.id, "success", ""))
            except discord.Forbidden:
                failed += 1
                rows.append((ch.name, ch.id, "forbidden", "Missing permissions / hierarchy"))
            except discord.HTTPException as e:
                failed += 1
                rows.append((ch.name, ch.id, "error", str(e)))

            # be gentle with rate limits
            await asyncio.sleep(0.2)

        # CSV report
        sio = io.StringIO(newline="")
        writer = csv.writer(sio, lineterminator="\n")
        writer.writerow(["channel_name", "channel_id", "status", "note"])
        writer.writerows(rows)
        data = io.BytesIO(sio.getvalue().encode("utf-8"))

        msg = (
            f"**Bulk permission change complete**\n"
            f"Target: `{getattr(target, 'name', str(target))}` (`{target.id}`)\n"
            f"Action: `{action.name}` → `{permission} = {value}`\n"
            f"Channels: **{len(guild.channels)}**  |  ✅ {success}  ❌ {failed}"
        )
        await interaction.followup.send(
            content=msg,
            file=discord.File(data, filename=f"bulk_perm_change_{permission}_{action.value}.csv"),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BulkPermChange(bot))
