# cogs/keepRemove
import os
import io
import csv
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def permCheck(interaction: discord.Interaction) -> bool:
    # Admins or developer
    if interaction.user and interaction.user.id == DEV_ID:
        return True
    if interaction.guild and isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False

class keepRemove(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="keepremove",
        description="Remove a role from all users who dont have given a specified role."
    )
    @app_commands.describe(
        role_to_remove="Role to remove from members",
        keep_role="Only members WITHOUT this role keep the role; others lose it",
        dry_run="If true, shows who would be changed without actually removing"
    )
    @app_commands.check(permCheck)
    @app_commands.guild_only()
    async def prunerole(
        self,
        interaction: discord.Interaction,
        role_to_remove: discord.Role,
        keep_role: discord.Role,
        dry_run: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("Use this in a server.", ephemeral=True)

        # make sure user isnt stupid
        if role_to_remove == keep_role:
            return await interaction.followup.send("`role_to_remove` and `keep_role` must be different.", ephemeral=True)
        if role_to_remove.is_default():
            return await interaction.followup.send("You can't remove the **@everyone** role.", ephemeral=True)

        # Permissions / hierarchy
        me: discord.Member = guild.me
        if not me.guild_permissions.manage_roles:
            return await interaction.followup.send("I need **Manage Roles** permission.", ephemeral=True)
        if role_to_remove.managed:
            return await interaction.followup.send("`role_to_remove` is **managed** and can't be changed by bots.", ephemeral=True)
        if me.top_role <= role_to_remove:
            return await interaction.followup.send(
                f"I can't modify `{role_to_remove.name}` because it's higher or equal to my top role.",
                ephemeral=True
            )

        # Warm member cache so checks are accurate
        try:
            async for _ in guild.fetch_members(limit=None):
                pass
        except discord.Forbidden:
            return await interaction.followup.send(
                "Missing permission to view members or **Server Members Intent** isn't enabled.", ephemeral=True
            )

        # Find targets: members who HAVE role_to_remove AND DO NOT HAVE keep_role
        targets = [m for m in guild.members if (role_to_remove in m.roles and keep_role in m.roles)]

        # Build CSV
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["user_id", "username", "display_name", "will_remove"])
        for m in targets:
            writer.writerow([m.id, m.name, m.display_name or "", "yes"])
        data = io.BytesIO(out.getvalue().encode("utf-8"))

        if dry_run:
            return await interaction.followup.send(
                content=(
                    f"**Dry run** for `{role_to_remove.name}` → remove from members **without** `{keep_role.name}`\n"
                    f"Would affect: **{len(targets)}** member(s)."
                ),
                file=discord.File(data, filename=f"prune_preview_{role_to_remove.name.replace(' ','_')}.csv"),
                ephemeral=True,
            )

        # Apply changes
        removed = 0
        failed = 0
        for i, member in enumerate(targets, start=1):
            try:
                await member.remove_roles(role_to_remove, reason=f"Prune by {interaction.user} (missing {keep_role.name})")
                removed += 1
            except discord.Forbidden:
                failed += 1
            except discord.HTTPException:
                failed += 1

            if i % 10 == 0:
                await asyncio.sleep(0.5)  # be gentle with rate limits

        # Return summary + CSV of who was processed
        await interaction.followup.send(
            content=(
                f"Removed `{role_to_remove.name}` from members **without** `{keep_role.name}`.\n"
                f"✅ Removed: **{removed}**\n"
                f"❌ Failed: **{failed}**"
            ),
            file=discord.File(data, filename=f"pruned_{role_to_remove.name.replace(' ','_')}.csv"),
            ephemeral=True,
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(keepRemove(bot))
