Its a Discord bot that does.... stuff. I'll add stuff as I find a use for it, generally it has various administrative utilities for Discord server auditing.

# Requirements
discord.py>=2.4
python-dotenv>=1.0
aiohttp>=3.9

# Setup information
1. Make a Discord Application and bot account in the [Dev Portal](https://discord.com/developers/applications)
2. Invite the bot to your server using `https://discordapp.com/oauth2/authorize?client_id=CLIENT_ID&scope=bot`, just make sure to put the actual bot's client ID instead of `CLIENT_ID`
3. Download the code from here
4. Make a file in the main folder called .env
5. Within .env make 3 lines
    DISCORD_BOT_TOKEN= [Insert your token here]
    TESTING_GUILD_ID= [Insert your testing server ID here]
    DEV_ID= [Insert your UUID here]
6. Run main.py in your command line
7. Profit?


I'm not making this into a whole thing, if you need help google it or use AI, idc, it's not my problem lol.