import os, io, csv, discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def permCheck(interaction: discord.Interaction):
    if interaction.user and interaction.user.id == DEV_ID:
        return True
    if interaction.guild and isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False

class PermissionChecker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="checkperms",
        description="Export roles, channels, or both with a given permission"
    )
    @app_commands.describe(
        permission_name="Permission name, e.g. administrator, manage_messages, ban_members",
        scope="Choose whether to check roles, channels, or both"
    )
    @app_commands.choices(scope=[
        app_commands.Choice(name="Roles only", value="roles"),
        app_commands.Choice(name="Channels only", value="channels"),
        app_commands.Choice(name="Both roles and channels", value="both"),
    ])
    @app_commands.check(permCheck)
    @app_commands.guild_only()
    async def checkperms(
        self,
        interaction: discord.Interaction,
        permission_name: str,
        scope: app_commands.Choice[str],
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("Use this in a server.", ephemeral=True)

        perm_flag = permission_name.strip().lower().replace(" ", "_")

        if perm_flag not in discord.Permissions.VALID_FLAGS:
            valid = ", ".join(sorted(discord.Permissions.VALID_FLAGS))
            return await interaction.followup.send(
                f"`{permission_name}` is not a valid permission.\n\n"
                f"Valid permissions:\n{valid}",
                ephemeral=True,
            )

        files = []
        messages = []

        # Check roles
        if scope.value in ("roles", "both"):
            matching_roles = []

            roles_iter = list(guild.roles)
            if guild.default_role not in roles_iter:
                roles_iter.append(guild.default_role)

            for role in roles_iter:
                if getattr(role.permissions, perm_flag, False):
                    matching_roles.append((role.id, role.name))

            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["Role ID", "Role Name"])
            writer.writerows(matching_roles)

            csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
            files.append(discord.File(csv_bytes, filename=f"roles_with_{perm_flag}.csv"))
            messages.append(f"Found **{len(matching_roles)}** role(s) with `{perm_flag}`.")

        # Check channels
        if scope.value in ("channels", "both"):
            matching_channels = []

            for channel in guild.channels:
                overwrites = channel.overwrites

                for target, overwrite in overwrites.items():
                    allowed, denied = overwrite.pair()

                    if getattr(allowed, perm_flag, False):
                        target_type = "Role" if isinstance(target, discord.Role) else "Member"
                        matching_channels.append((
                            channel.id,
                            channel.name,
                            str(channel.type),
                            target_type,
                            target.id,
                            getattr(target, "name", str(target)),
                        ))

            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow([
                "Channel ID",
                "Channel Name",
                "Channel Type",
                "Target Type",
                "Target ID",
                "Target Name",
            ])
            writer.writerows(matching_channels)

            csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
            files.append(discord.File(csv_bytes, filename=f"channels_with_{perm_flag}.csv"))
            messages.append(f"Found **{len(matching_channels)}** channel overwrite(s) allowing `{perm_flag}`.")

        await interaction.followup.send(
            content="\n".join(messages),
            files=files,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PermissionChecker(bot))