import json, os, time

import discord
from discord.ext import commands as dcmds

intents = discord.Intents.default()
intents.members = True

songbot = dcmds.Bot(command_prefix=dcmds.when_mentioned, intents=intents)

@songbot.listen('on_ready')
async def announce_ready():
    print(f"logged in as {songbot.user}")

async def testcmd(ctx):
    if ctx.message.reference is not None:
        await ctx.send("that message references something")
        refmsg = await ctx.fetch_message(ctx.message.reference.message_id)
        print(refmsg.id)
        print(len(refmsg.embeds))
        for embed in refmsg.embeds:
            print(embed.url)

@songbot.command()
async def respotify(ctx):
    """ Reload the Spotify component. """
    async with ctx.typing():
        songbot.reload_extension('spotifycog')

if __name__ == "__main__":
    print("starting slurper")
    with open("secrets.json", 'r') as secretsfile:
        secrets = json.load(secretsfile)
        for k in secrets.keys():
            os.environ[k] = secrets[k]
    if not os.path.isdir("slurper_state"):
        os.mkdir("slurper_state")
    
    songbot.load_extension('spotifycog')
    songbot.run(os.environ["DISCORD_CLIENT_SECRET"]) 