import discord
from discord import app_commands
from discord.ext import commands

class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency") #adds command
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"PONG! {round(self.bot.latency*1000,2)} ms", ephemeral=True) #response with the ping

async def setup(bot: commands.Bot): #adds the cog to the bot
    await bot.add_cog(Ping(bot))