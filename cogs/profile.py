import os
import discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def is_dev(interaction: discord.Interaction) -> bool:
    return bool(interaction.user and interaction.user.id == DEV_ID)

class profile(commands.GroupCog):
    profile = app_commands.Group(name="profile", description="Change the bot's avatar or status (bio/banner unsupported)")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # /admin profile set
    @profile.command(
        name="set",
        description="Dev only: change the bot's avatar (global/server) or status. Bio/Banner are not supported for bots."
    )
    @app_commands.choices(
        target=[
            app_commands.Choice(name="Avatar (global)", value="avatar_global"),
            app_commands.Choice(name="Avatar (server)", value="avatar_guild"),
            app_commands.Choice(name="Status / Presence", value="status"),
            app_commands.Choice(name="Bio (About Me) — Not Supported", value="bio"),
            app_commands.Choice(name="Banner — Not Supported", value="banner"),
        ],
        status=[
            app_commands.Choice(name="online", value="online"),
            app_commands.Choice(name="idle", value="idle"),
            app_commands.Choice(name="dnd", value="dnd"),
            app_commands.Choice(name="invisible", value="invisible"),
        ],
        activity_type=[
            app_commands.Choice(name="Playing", value="playing"),
            app_commands.Choice(name="Watching", value="watching"),
            app_commands.Choice(name="Listening", value="listening"),
            app_commands.Choice(name="Competing", value="competing"),
            app_commands.Choice(name="Streaming", value="streaming"),
        ],
    )
    @app_commands.describe(
        target="What do you want to change?",
        image="Attach an image for avatar changes (PNG/JPG/WebP/GIF)",
        guild_id="For server avatar: target guild ID (optional; defaults to current server)",
        status="For status: online / idle / dnd / invisible",
        activity_type="For status: choose an activity type",
        activity_text="For status: activity text (e.g., 'with roles')",
        stream_url="For status Streaming: URL (required for Streaming presence)"
    )
    @app_commands.check(is_dev)
    async def ping(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        image: discord.Attachment | None = None,
        guild_id: str | None = None,
        status: app_commands.Choice[str] | None = None,
        activity_type: app_commands.Choice[str] | None = None,
        activity_text: str | None = None,
        stream_url: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        choice = target.value

        # ---- Unsupported: Bio/Banner ----
        if choice in {"bio", "banner"}:
            return await interaction.followup.send(
                "❌ **Not supported for bots via Discord’s public API.**\n"
                "- **Bio (About Me)** and **Profile Banner** cannot be changed programmatically by bots.\n"
                "- For visuals, use the Developer Portal/app settings instead.",
                ephemeral=True,
            )

        # ---- Avatar (global) ----
        if choice == "avatar_global":
            if not image:
                return await interaction.followup.send(
                    "Attach an `image` to set the global avatar.", ephemeral=True
                )
            if not image.content_type or not image.content_type.startswith("image/"):
                return await interaction.followup.send("The attachment must be an image.", ephemeral=True)

            data = await image.read()
            try:
                await self.bot.user.edit(avatar=data)
                return await interaction.followup.send("✅ Global avatar updated.", ephemeral=True)
            except discord.HTTPException as e:
                return await interaction.followup.send(f"❌ Failed to update global avatar: {e}", ephemeral=True)

        # ---- Avatar (server) ----
        if choice == "avatar_guild":
            if not image:
                return await interaction.followup.send(
                    "Attach an `image` to set the **server-specific** avatar.", ephemeral=True
                )
            if not image.content_type or not image.content_type.startswith("image/"):
                return await interaction.followup.send("The attachment must be an image.", ephemeral=True)

            # Determine target guild
            if guild_id:
                try:
                    gid = int(guild_id)
                except ValueError:
                    return await interaction.followup.send("❌ `guild_id` must be a number.", ephemeral=True)
            else:
                if not interaction.guild:
                    return await interaction.followup.send(
                        "❌ Use this in a server channel or provide `guild_id`.", ephemeral=True
                    )
                gid = interaction.guild.id

            guild = self.bot.get_guild(gid)
            if guild is None:
                return await interaction.followup.send(
                    f"❌ I’m not in guild `{gid}` (or it’s not cached).", ephemeral=True
                )

            me = guild.me  # bot's Guild Member
            if me is None:
                return await interaction.followup.send("❌ Could not resolve bot member for this guild.", ephemeral=True)

            data = await image.read()
            try:
                # Member.edit supports guild avatar for bots (server-specific avatar)
                await me.edit(avatar=data)
                return await interaction.followup.send(
                    f"✅ Server avatar updated for **{guild.name}** ({gid}).", ephemeral=True
                )
            except discord.HTTPException as e:
                return await interaction.followup.send(f"❌ Failed to update server avatar: {e}", ephemeral=True)

        # ---- Status / Presence (global) ----
        if choice == "status":
            # Map status
            status_map = {
                "online": discord.Status.online,
                "idle": discord.Status.idle,
                "dnd": discord.Status.do_not_disturb,
                "invisible": discord.Status.invisible,
            }
            dstatus = status_map.get(status.value) if status else discord.Status.online

            # Build optional activity
            activity = None
            if activity_type and activity_text:
                kind = activity_type.value
                if kind == "playing":
                    activity = discord.Game(name=activity_text)
                elif kind == "watching":
                    activity = discord.Activity(type=discord.ActivityType.watching, name=activity_text)
                elif kind == "listening":
                    activity = discord.Activity(type=discord.ActivityType.listening, name=activity_text)
                elif kind == "competing":
                    activity = discord.Activity(type=discord.ActivityType.competing, name=activity_text)
                elif kind == "streaming":
                    if not stream_url:
                        return await interaction.followup.send(
                            "Provide a `stream_url` (e.g., https://twitch.tv/yourchannel) for streaming presence.",
                            ephemeral=True,
                        )
                    activity = discord.Streaming(name=activity_text or "Streaming", url=stream_url)

            try:
                await self.bot.change_presence(status=dstatus, activity=activity)
                return await interaction.followup.send("✅ Status/presence updated.", ephemeral=True)
            except discord.HTTPException as e:
                return await interaction.followup.send(f"❌ Failed to update presence: {e}", ephemeral=True)

        # Fallback
        return await interaction.followup.send("❌ Unknown target.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(profile(bot))
