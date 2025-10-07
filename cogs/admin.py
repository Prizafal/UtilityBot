import os, os.path, discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def is_dev(interaction: discord.Interaction):
    return bool(interaction.user and interaction.user.id == DEV_ID)

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command( # overall command name and description
        name="admin",
        description="Dev only: sync commands or manage cogs (one command with options)"
    )
    @app_commands.choices( # sub command options, value is the function that it calls
        action=[
            app_commands.Choice(name="Sync (server)", value="sync_server"),
            app_commands.Choice(name="Sync (global)", value="sync_global"),
            app_commands.Choice(name="Reload one cog", value="reload_cog"),
            app_commands.Choice(name="Load one cog", value="load_cog"),
            app_commands.Choice(name="Unload one cog", value="unload_cog"),
            app_commands.Choice(name="Reload all cogs", value="reload_all_cogs"),
            app_commands.Choice(name="List loaded cogs", value="list_cogs"),
        ]
    )
    @app_commands.describe(  # descriptions for the the fields you can enter, in order  of appearance
        action="Pick what to do",  #always selected
        cog="Cog module (e.g., cogs.ping). Autocomplete available when needed.", # only for cog actions, leave blank otherwise
        guild_id="For server sync: specify a guild ID (optional; defaults to current guild)" #only needed for server sync
    )
    @app_commands.check(is_dev) #permission check to only the dev to run the admin commands, safety stuff
    async def admin( #makes command
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        cog: str | None = None,
        guild_id: str | None = None,
    ):
        act = action.value

        # ---- Sync (server) ----
        if act == "sync_server":
            if guild_id: # input validation for guild ID
                try:
                    target_id = int(guild_id)
                except ValueError:
                    return await interaction.response.send_message("`guild_id` must be a number.", ephemeral=True)
            else:
                if not interaction.guild: # if no guild ID provided, throws error saying be in a server. If in server and no ID provided, uses the server you're in
                    return await interaction.response.send_message(
                        "Use this in a server channel or provide `guild_id`.", ephemeral=True
                    )
                target_id = interaction.guild.id

            target_guild = self.bot.get_guild(target_id)
            if target_guild is None:
                return await interaction.response.send_message(
                    f"Bot not in guild `{target_id}` (or it’s not cached).", ephemeral=True #error if the bot cant find the server ID provided
                )

            synced = await self.bot.tree.sync(guild=discord.Object(id=target_id)) #actual fucntion to sync commands to a server
            return await interaction.response.send_message(
                f"Synced **{len(synced)}** command(s) to **{target_guild.name}** (`{target_id}`).",
                ephemeral=True,
            )

        # ---- Sync (global) ----
        if act == "sync_global":
            synced = await self.bot.tree.sync()
            return await interaction.response.send_message(
                f"🌍 Synced **{len(synced)}** global command(s).", ephemeral=True
            )

        # ---- Reload all cogs ----
        if act == "reload_all_cogs":
            await interaction.response.defer(ephemeral=True)
            count = 0
            errors: list[str] = []
            for ext in list(self.bot.extensions.keys()): #loop for all servers a bot is in
                if not ext.startswith("cogs."):
                    continue
                try:
                    await self.bot.reload_extension(ext)
                    count += 1
                except Exception as e:
                    errors.append(f"`{ext}` → {type(e).__name__}: {e}")
            msg = f"Reloaded **{count}** cog(s)." # confirmation message
            if errors:
                msg += "\n\n**Errors:**\n" + "\n".join(f"• {line}" for line in errors[:10]) #errors if applicable (hopefully wont be)
            return await interaction.followup.send(msg, ephemeral=True)

        # ---- List cogs ----
        if act == "list_cogs":
            loaded = sorted(self.bot.extensions.keys()) # puts all cogs the bot knows about into a list
            if not loaded:
                return await interaction.response.send_message("ℹNo cogs are loaded.", ephemeral=True) #error if no cogs are loaded (wont ever happen, this command is in a cog lol)
            formatted = "\n".join(f"• `{m}`" for m in loaded)
            return await interaction.response.send_message(f"**Loaded cogs:**\n{formatted}", ephemeral=True) #lists cogs from the cog list

        # ---- Single-cog actions ----
        if act in {"reload_cog", "load_cog", "unload_cog"}:
            if not cog: # error if the command is sent w/o a cog getting specified
                return await interaction.response.send_message(
                    "Provide a cog (e.g. `cogs.ping`). Tip: use autocomplete.", ephemeral=True
                )
            try:
                if act == "reload_cog": # should be self explanatory
                    await self.bot.reload_extension(cog)
                    msg = f"🔁 Reloaded `{cog}`"
                elif act == "load_cog":
                    await self.bot.load_extension(cog)
                    msg = f"Loaded `{cog}`"
                elif act == "unload_cog":
                    await self.bot.unload_extension(cog)
                    msg = f"Unloaded `{cog}`"
                else:
                    msg = "Unknown action. Congrats you broke it."
                return await interaction.response.send_message(msg, ephemeral=True)
            except Exception as e:
                return await interaction.response.send_message(f"{type(e).__name__}: {e}", ephemeral=True)  #error handling for cog actions
        await interaction.response.send_message("Unknown action. You **really** broke it.", ephemeral=True) #error that only occurs if you somehow skip all the try's

    # ---------- Autocompletes ----------
    @admin.autocomplete("cog") #autocomplete for cog names
    async def cog_autocomplete(self, interaction: discord.Interaction, current: str):
        current = (current or "").lower()
        seen = set()
        suggestions: list[app_commands.Choice[str]] = []

        # loaded
        for ext in sorted(self.bot.extensions.keys()):
            if current in ext.lower() and ext not in seen:
                suggestions.append(app_commands.Choice(name=ext, value=ext))
                seen.add(ext)
                if len(suggestions) >= 25:
                    return suggestions

        # discovers files in folder called cogs, if a given file wasnt already loaded
        cogs_dir = os.path.join(os.getcwd(), "cogs")
        try:
            for fname in sorted(os.listdir(cogs_dir)):
                if fname.endswith(".py") and not fname.startswith("_"):
                    mod = f"cogs.{fname[:-3]}"
                    if current in mod.lower() and mod not in seen:
                        suggestions.append(app_commands.Choice(name=mod, value=mod))
                        seen.add(mod)
                        if len(suggestions) >= 25:
                            break
        except FileNotFoundError:
            pass
        return suggestions

    @admin.autocomplete("guild_id") # autocomplete for guild ID
    async def guild_id_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete guild IDs by name or ID (for sync server)."""
        q = (current or "").lower()
        out: list[app_commands.Choice[str]] = []
        for g in self.bot.guilds:
            if q in g.name.lower() or q in str(g.id):
                out.append(app_commands.Choice(name=f"{g.name} ({g.id})", value=str(g.id)))
            if len(out) >= 25:
                break
        return out

async def setup(bot: commands.Bot): #adds the cog to the bot
    await bot.add_cog(Admin(bot))
