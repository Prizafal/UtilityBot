import os, io, csv, discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def permCheck(interaction: discord.Interaction): #checks if the user is an admin or the developer
    if interaction.user and interaction.user.id == DEV_ID:
        return True
    if interaction.guild and isinstance(interaction.user, (discord.Member,)):
        return interaction.user.guild_permissions.administrator
    return False

class PermissionChecker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(  #creates command with description
        name="checkroles",
        description="Export all roles with a given permission (includes @everyone) to CSV"
    )
    @app_commands.describe( #creates secondary description for selecting a permission
        permission_name="Permission name (e.g., administrator, manage_messages, ban_members)"
    )
    @app_commands.check(permCheck)  # runs permission check
    @app_commands.guild_only()
    async def checkroles(
        self,
        interaction: discord.Interaction,
        permission_name: str,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("Use this in a server.", ephemeral=True)

        # Permission validation
        perm_flag = permission_name.strip().lower().replace(" ", "_")
        if perm_flag not in discord.Permissions.VALID_FLAGS:
            valid = ", ".join(sorted(discord.Permissions.VALID_FLAGS))
            return await interaction.followup.send(
                f"`{permission_name}` is not a valid permission.\n"
                f"Valid permissions:\n{valid}",
                ephemeral=True,
            )

        # Gets all roles in server
        roles_iter = list(guild.roles)
        if guild.default_role not in roles_iter:
            roles_iter.append(guild.default_role)  #extra check to make sure @everyone is included

        matching: list[tuple[int, str]] = [] #iterates through all roles for check
        for role in roles_iter:
            if getattr(role.permissions, perm_flag, False):
                matching.append((role.id, role.name))

        # Make the CSV
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["Role ID", "Role Name"])
        writer.writerows(matching)
        csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
        fname = f"roles_with_{perm_flag}.csv"

        await interaction.followup.send( #sends the csv file
            content=f"Found **{len(matching)}** role(s) with `{perm_flag}`.",
            file=discord.File(csv_bytes, filename=fname),
            ephemeral=True,
        )

async def setup(bot: commands.Bot): #adds the cog to the bot
    await bot.add_cog(PermissionChecker(bot))
