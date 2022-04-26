import dbm
import json
import os
from sqlalchemy import MetaData, Table, Column, Integer, String
from sqlalchemy import create_engine

import discord
from discord.ext import commands as dcmds

###
# set up logging
###
import logging
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
discord_log = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
discord_log.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log)

songbot_logger = logging.getLogger('songbot')
songbot_logger.setLevel(logging.DEBUG)
songbot_log = logging.FileHandler(filename='songbot.log', encoding='utf-8', mode='w')
songbot_log.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
songbot_logger.addHandler(songbot_log)
###
# set up discord bot intents
###

intents = discord.Intents.default()
intents.members = True
songbot = dcmds.Bot(command_prefix=dcmds.when_mentioned, intents=intents)

###
# set up database engine
###

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

songbot.dbmeta = dbmeta
songbot.recs_table = recs_table
songbot.dbengine = dbengine

###
# various listeners and bot things
###

@songbot.listen('on_ready')
async def announce_ready():
    print(f"logged in as {songbot.user}")

@songbot.command()
async def reset(ctx):
    """ Reload all components. """
    async with ctx.typing():
        songbot.reload_extension('songcog')
        songbot.reload_extension('playlistscog')


if __name__ == "__main__":
    print("starting slurper")
    with open("secrets.json", 'r') as secretsfile:
        secrets = json.load(secretsfile)
        for k in secrets.keys():
            os.environ[k] = secrets[k]
    if not os.path.isdir("slurper_state"):
        os.mkdir("slurper_state")

    songbot.load_extension('songcog')
    songbot.load_extension('playlistscog')
    songbot.run(os.environ["DISCORD_CLIENT_SECRET"])
