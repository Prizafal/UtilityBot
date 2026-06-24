import discord
from discord import app_commands
from discord.ext import commands

@app_commands.command(
    name="botinfo",
    description="Provides information about the bot"
)
async def botinfo(self, interaction: discord.Interaction):
    embed = discord.Embed(
        title="UtilityBot Information",
        description=(
            "Originally programmed by **[Prizafal](https://prizafal.com)**.\n"
            "This instance is operated by **Prizafal**."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="Privacy Policy",
        value="https://github.com/Prizafal/UtilityBot/blob/main/privacyPolicy.txt",
        inline=False
    )

    embed.add_field(
        name="Source Code",
        value="https://github.com/Prizafal/UtilityBot",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )
async def setup(bot: commands.Bot):
    await bot.add_cog(botinfo(bot))