import json
import os
import time
from sqlalchemy import MetaData, Table, Column, Integer, String
from sqlalchemy import create_engine

import discord
from discord.ext import commands as dcmds

intents = discord.Intents.default()
intents.members = True

songbot = dcmds.Bot(command_prefix=dcmds.when_mentioned, intents=intents)
dbengine = create_engine(
    "sqlite+pysqlite:///slurper_state/recommendations.db", echo=True, future=True)
dbmeta = MetaData()
recs_table = Table("recommendations", dbmeta, 
                   Column("id", Integer, primary_key=True),
                   Column("resource_type", String),
                   Column("uri", String),
                   Column("guild", Integer),
                   Column("channel", Integer),
                   Column("user", Integer),
                   Column("timestamp", String))
dbmeta.create_all(dbengine)

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
        forward_dbengine()

def forward_dbengine():
    spcog = songbot.get_cog('Spotify')
    if spcog:
        spcog.dbengine = dbengine
        spcog.dbmeta = dbmeta
        spcog.recs_table = recs_table


if __name__ == "__main__":
    print("starting slurper")
    with open("secrets.json", 'r') as secretsfile:
        secrets = json.load(secretsfile)
        for k in secrets.keys():
            os.environ[k] = secrets[k]
    if not os.path.isdir("slurper_state"):
        os.mkdir("slurper_state")

    songbot.load_extension('spotifycog')
    forward_dbengine()
    songbot.run(os.environ["DISCORD_CLIENT_SECRET"])
