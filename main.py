import os, asyncio, logging, logging.handlers, discord
from dotenv import load_dotenv
from discord.ext import commands

# ---------- env ----------
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TESTING_GUILD_ID = os.getenv("TESTING_GUILD_ID", "").strip()
TESTING_GUILD = int(TESTING_GUILD_ID) if TESTING_GUILD_ID.isdigit() else None

if not TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN in .env")

# ---------- intents ----------
INTENTS = discord.Intents.default()
INTENTS.guilds = True
INTENTS.members = True
INTENTS.message_content = True #feel free to turn these on and off if needed

# ---------- cogs ----------
COGS = [  #if you add a new cog, add it here
    "cogs.exportrole",
    "cogs.ping",
    "cogs.admin",
    "cogs.permissionCheck"
]

class Bot(commands.Bot): #generally creates the bot
    def __init__(self, testing_guild_id: int | None):
        super().__init__(command_prefix=commands.when_mentioned, intents=INTENTS)
        self.testing_guild_id = testing_guild_id

    async def setup_hook(self):
        for ext in COGS: # cog loader
            try:
                await self.load_extension(ext)
                print(f"[COG] Loaded {ext}")
            except Exception as e:
                print(f"[COG] FAILED {ext}: {e}")

        if self.testing_guild_id: #syncs commands to testing guilds upon boot
            guild = discord.Object(id=self.testing_guild_id)
            self.tree.clear_commands(guild=guild)
            self.tree.copy_global_to(guild=guild)  # optional mirror
            synced = await self.tree.sync(guild=guild)
            print(f"[SYNC] Cleared + registered {len(synced)} cmd(s) → testing guild {self.testing_guild_id}")

        # 3) If you also want to sync every joined guild, do it AFTER ready in a background task
        else:
            self.loop.create_task(self._sync_all_guilds_after_ready())

    async def _sync_all_guilds_after_ready(self): #syncs commands to all guilds, occurs after the test guild boot
        await self.wait_until_ready()
        print("[DBG] joined guilds:", [(g.name, g.id) for g in self.guilds])
        for g in self.guilds:
            try:
                synced = await self.tree.sync(guild=discord.Object(id=g.id))
                print(f"[SYNC] {len(synced)} cmd(s) → {g.name} ({g.id})")
            except Exception as e:
                print(f"[SYNC] FAILED for {g.name} ({g.id}): {e}")

    async def on_ready(self): #success message
        print(f"Logged in as {self.user} ({self.user.id})")

    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command): #CLI command logging
        user = f"{interaction.user} ({interaction.user.id})"
        guild = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
        print(f"[CMD] {user} ran /{command.qualified_name} in {guild}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):#CLI error logging
        user = f"{interaction.user} ({interaction.user.id})"
        guild = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
        print(f"[CMD ERROR] {user} tried /{interaction.command.qualified_name} in {guild} → {error}")

def setup_logging(): #Create a log.txt file for errors and stuff
    logger = logging.getLogger("discord")
    logger.setLevel(logging.INFO)
    h = logging.handlers.RotatingFileHandler(
        "discord.log", encoding="utf-8", maxBytes=32 * 1024 * 1024, backupCount=5
    )
    fmt = logging.Formatter("[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{")
    h.setFormatter(fmt)
    logger.addHandler(h)

async def main(): #main function to start the bot
    setup_logging()
    try:
        async with Bot(testing_guild_id=TESTING_GUILD) as bot:
            await bot.start(TOKEN)
    except discord.LoginFailure as e: #error handling for login issues
        print(f"[LOGIN] Failed: {e}")
    except Exception as e:
        print(f"[FATAL] {e}")

if __name__ == "__main__":
    asyncio.run(main())