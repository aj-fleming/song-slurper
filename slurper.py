import discord
from discord.ext import commands as dcmds
import json

intents = discord.Intents.default()
intents.members = True

songbot = dcmds.Bot(command_prefix=dcmds.when_mentioned, intents=intents)

@songbot.event
async def on_ready():
    print(f"logged in as {songbot.user}")

@songbot.event
async def on_message(msg):
    # don't forget to process commands on this message
    # in fact, we should do that first...
    await songbot.process_commands(msg)

    if msg.author.id == songbot.user.id:
        return
    if msg.content == "pingus":
        await msg.channel.send("pongus")

@songbot.event
async def on_command(ctx):
    print(f"command {ctx.command} invoked in {ctx.channel.name}")

@songbot.command()
async def slurp(ctx):
    """tells the song slurper to listen on this channel"""
    print("slurpin'")
    await ctx.send(f"now slurping songs from {ctx.channel}")

@songbot.command()
async def testcmd(ctx):
    if ctx.message.reference is not None:
        await ctx.send("that message references something")
        refmsg = await ctx.fetch_message(ctx.message.reference.message_id)
        print(refmsg.id)
        print(len(refmsg.embeds))


if __name__ == "__main__":
    print("starting slurper")
    with open("secrets.json", 'r') as secrets:
        secrets_dict = json.load(secrets)
    for cmd in songbot.commands:
        print(cmd.name)
    songbot.run(secrets_dict["discord_key"]) 