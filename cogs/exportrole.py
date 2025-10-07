import io, os, csv, datetime
import discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

class ExportRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def permCheck(interaction: discord.Interaction): #checks if the user is an admin or the developer
        if interaction.user and interaction.user.id == DEV_ID:
            return True
        if interaction.guild and isinstance(interaction.user, (discord.Member,)):
            return interaction.user.guild_permissions.administrator
        return False

    @app_commands.command(name="exportrole", description="Export members in a role to CSV") #command info and description
    @app_commands.describe(role="Role to export")
    @app_commands.check(permCheck)  # runs permission check
    @app_commands.guild_only() #makes the command only work in a server

    async def exportrole(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None: # secondary check to make sure its only ran in a guild
            return await interaction.followup.send("Use this in a server.", ephemeral=True)
        try:
            async for _ in guild.fetch_members(limit=None):
                pass
        except discord.Forbidden: # erorr handling for no member intent
            return await interaction.followup.send(
                "Enable **Server Members Intent** and ensure I can view members.", ephemeral=True
            )

        members = list(role.members) #adds members of the defined role to a list

        #all of this is getting it to output to csv nicely
        def iso(dt: datetime.datetime | None) -> str:
            return dt.isoformat() if isinstance(dt, datetime.datetime) else ""

        out = io.StringIO(newline="")
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["user_id","username","display_name","nickname"])
        for m in sorted(members, key=lambda x: (x.display_name or x.name).lower()):
            w.writerow([m.id, m.name, m.display_name or "", m.nick or ""])

        data = io.BytesIO(out.getvalue().encode("utf-8"))
        await interaction.followup.send(
            content=f"Found **{len(members)}** member(s) in `{role.name}`.",
            file=discord.File(data, filename=f"role_export_{role.name.replace(' ','_')}.csv"),
            ephemeral=True
        )

async def setup(bot: commands.Bot): #adds the cog to the bot
    await bot.add_cog(ExportRole(bot))