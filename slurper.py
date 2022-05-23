import json
import os
from sqlalchemy import MetaData, Table, Column, BigInteger, Integer, String, DateTime
from sqlalchemy.ext.asyncio import create_async_engine

import discord
from discord.ext import commands as dcmds

###
# set up logging
###
import logging
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
discord_log = logging.FileHandler(
    filename='discord.log', encoding='utf-8', mode='w')
discord_log.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log)

songbot_logger = logging.getLogger('songbot')
songbot_logger.setLevel(logging.DEBUG)
songbot_log = logging.FileHandler(
    filename='songbot.log', encoding='utf-8', mode='w')
songbot_log.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
songbot_logger.addHandler(songbot_log)
logging.getLogger('sqlalchemy.engine').addHandler(songbot_log)
###
# set up discord bot intents
###

intents = discord.Intents.default()
intents.members = True
songbot = dcmds.Bot(command_prefix=dcmds.when_mentioned, intents=intents)

###
# various listeners and bot things
###


@songbot.listen('on_ready')
async def announce_ready():
    songbot_logger.info(f"logged in as {songbot.user}")
    songbot.load_extension('songcog')
    songbot.load_extension('playlistscog')


@songbot.command()
async def reset(ctx):
    """ Reload all components. """
    async with ctx.typing():
        songbot.get_cog('Song Saving').songs_db_inserter.cancel()
        songbot.reload_extension('songcog')
        songbot.reload_extension('playlistscog')


if __name__ == "__main__":
    songbot_logger.info("starting up slurper")
    with open("secrets.json", 'r') as secretsfile:
        secrets = json.load(secretsfile)
        for k in secrets.keys():
            os.environ[k] = secrets[k]
    if not os.path.isdir("slurper_state"):
        os.mkdir("slurper_state")

    ###
    # set up database engine
    ###
    dbengine = create_async_engine(
        "postgresql+asyncpg://songbot:s0ngz@localhost/songsdb", future=True)
    dbmeta = MetaData()
    recs_table = Table("recommendations", dbmeta,
                       Column("id", Integer, primary_key=True, autoincrement="auto"),
                       Column("resource_type", String),
                       Column("uri", String),
                       Column("guild", BigInteger),
                       Column("channel", BigInteger),
                       Column("message", BigInteger),
                       Column("user", BigInteger),
                       Column("timestamp", DateTime))
                       
    plist_table = Table("playlists", dbmeta,
                        Column("id", Integer, primary_key=True),
                        Column("media_type", String),
                        Column("uri", String),
                        Column("guild", BigInteger),
                        Column("creation_timestamp", DateTime))

    songbot.dbmeta = dbmeta
    songbot.recs_table = recs_table
    songbot.dbengine = dbengine

    async def setup_db():
        async with dbengine.begin() as conn:
            await conn.run_sync(dbmeta.drop_all)
            await conn.run_sync(dbmeta.create_all)

    songbot.loop.create_task(setup_db())
    songbot.run(os.environ["DISCORD_CLIENT_SECRET"])
