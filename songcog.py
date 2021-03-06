import asyncio
import json
import logging
import os

import discord
from discord.ext import commands, tasks
import pandas as pd
from requests import JSONDecodeError
import sqlalchemy as sqla


from helpers import SpotifyURI, is_valid_spotify_uri

_STATE_DIR = "slurper_state"
_SPOTIFY_STATE_FILENAME = "spotify.json"
_SPOTIFY_STATE = os.path.join(_STATE_DIR, _SPOTIFY_STATE_FILENAME)
_RECS_DB = "recommendations.db"

song_logger = logging.getLogger('songbot.saving')


class SongSavingCog(commands.Cog, name="Song Saving"):
    def __init__(self, bot):
        # set up clean state
        self.bot = bot
        self.bot.state = {}
        self.dblock = asyncio.Lock()
        # load previous state
        if os.path.isfile("slurper_state/spotify.json"):
            try:
                self.bot.state = self.load_previous_state()
            except JSONDecodeError as json_error:
                song_logger.error(json_error)

        # songs: list of dicts matching the recommendations table schema
        self.songs = []
        self.songs_db_inserter.start()

    def load_previous_state(self):
        song_logger.info("Loading previous spotify cog state...")
        with open(_SPOTIFY_STATE) as statefile:
            old_state = json.load(statefile)
        new_state = {}
        for guild_id, infos in old_state.items():
            announcer = infos["announcer"]
            for k in announcer.keys():
                if not announcer[k]:
                    announcer[k] = 0
            new_state[int(guild_id)] = {  # need to switch from json string key to int for proper function
                "announcer": {
                    "discord_id": announcer["discord_id"],
                    "sp_user": announcer["sp_user"]
                },
                "listening_to": set(infos["listening_to"]),
                "announcing_in": set(infos["announcing_in"])
            }
        return new_state

    def cog_unload(self):
        song_logger.info("Saving Spotify cog state...")
        with open(_SPOTIFY_STATE, 'w+') as statefile:
            json.dump(self.bot.state, statefile, default=list)

    def add_new_guild(self, new_id):
        song_logger.info(f"now configured in guild {new_id}")
        self.bot.state.update({new_id: {"announcer": {"discord_id": 0, "sp_user": 0},
                                        "listening_to": set(), "announcing_in": set()}})

    async def collect_spotify_resources_from_msg(self, msg):
        song_logger.debug(
            f"found {len(msg.embeds)} embeds on message {msg.id}")
        spotify_uris = [u for u in
                        [SpotifyURI.from_link(e.url) for e in msg.embeds]
                        if is_valid_spotify_uri(u)]
        song_logger.debug(
            f"found {len(spotify_uris)} spotify embeds on {msg.id}")
        tstamp = pd.Timestamp(msg.created_at)
        songs = []
        for t in spotify_uris:
            song_logger.debug(f"saving spotify resource {t}")
            songs.append({"resource_type": t.resource_type,
                          "uri": t.identifier,
                          "guild": msg.guild.id,
                          "channel": msg.channel.id,
                          "message": msg.id,
                          "user": msg.author.id,
                          "timestamp": tstamp})
        return songs

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.id == self.bot.user.id:
            return
        if msg.guild.id in self.bot.state:
            if msg.channel.id not in self.bot.state[msg.guild.id]["listening_to"]:
                return
            if len(msg.embeds) > 0:
                self.songs.extend(await self.collect_spotify_resources_from_msg(msg))

    @commands.Cog.listener()
    async def on_message_edit(self, msg_old, msg_new):

        # If the number of embeds in the message has changed,
        # check to see if any of them are spotify embeds.

        if msg_old.author.id == self.bot.user.id:
            return
        if msg_old.guild.id in self.bot.state:
            if msg_old.channel.id not in self.bot.state[msg_old.guild.id]["listening_to"]:
                return

        if len(msg_old.embeds) < len(msg_new.embeds):
            self.songs.extend(await self.collect_spotify_resources_from_msg(msg_new))

    @commands.command()
    async def listen(self, ctx, *, channel: discord.TextChannel = None):
        """ Listen for song suggestions here, or in the provided channel."""
        if ctx.guild.id not in self.bot.state.keys():
            self.add_new_guild(ctx.guild.id)

        if not channel:
            channel = ctx.channel
        self.bot.state[ctx.guild.id]["listening_to"].add(channel.id)
        song_logger.info(
            f"now listening to channel {channel.id} in guild {ctx.guild.id}")
        await channel.send(f"I am now listening to recommendations in <#{channel.id}>")

    @commands.command()
    async def slurp(self, ctx, start_dt: str):
        """Load all messages and search for spotify attachments, then save them.

        Args:
            start_dt (str): ISO-parseable datetime string as the UTC timestamp of the earliest message to get.
            Set to "all" for all messages in channel (may take some time!)
        """
        if start_dt == "all":
            after = pd.Timestamp(ctx.channel.created_at)
        else:
            try:
                after = pd.Timestamp(start_dt)
            except:
                await ctx.send("Datetime unparseable!")
                return

        if ctx.guild.id not in self.bot.state.keys():
            return

        song_logger.info(
            f"searching in {ctx.channel.id} for songs attached to all messages after {after}")
        old_songs = []
        async with ctx.typing():
            async with self.bot.dbengine.begin() as conn:
                result = await conn.execute(sqla.select(self.bot.recs_table))
            data = pd.DataFrame(result.fetchall())
            if not data.empty:
                data = data.set_index("id")
            async for msg in ctx.channel.history(after=after.to_pydatetime()):
                # short circuiting saves us here
                if (data.empty or msg.id not in data["message"].values) and len(msg.embeds) > 0:
                    old_songs.extend(await self.collect_spotify_resources_from_msg(msg))
            async with self.bot.dbengine.begin() as conn:
                await conn.execute(sqla.insert(self.bot.recs_table, old_songs))
            song_logger.info(
                f"saved {len(old_songs)} songs from {ctx.channel.id} that were not in database")
            await ctx.send("Found {0} old recommendations sent after {1} that I didn't have!".format(
                len(old_songs), after.isoformat(sep=':', timespec='minutes')))

    @commands.command()
    async def announce(self, ctx, *, channel: discord.TextChannel = None):
        """ Announce playlist suggestions here, or in the provided channel."""
        if ctx.guild.id not in self.bot.state.keys():
            self.add_new_guild(ctx.guild.id)
        if not channel:
            channel = ctx.channel
        self.bot.state[ctx.guild.id]["announcing_in"].add(channel.id)
        song_logger.info(
            f"now announcing playlists to channel {channel.id} in guild {ctx.guild.id}")
        await channel.send(f"I am now announcing my playlists in <#{channel.id}>")

    @commands.command()
    async def channels(self, ctx):
        """ Shows the channels used in this server. """
        if ctx.guild.id not in self.bot.state.keys():
            await ctx.send("I am not configured to do anything in this server yet!")
        else:
            l_refs = ["<#{0}>".format(
                c) for c in self.bot.state[ctx.guild.id]["listening_to"]]
            r_refs = ["<#{0}>".format(
                c) for c in self.bot.state[ctx.guild.id]["announcing_in"]]
            await ctx.send("I am listening for recommendations in {0}. I am announcing playlists in {1}.".format(", ".join(l_refs), ", ".join(r_refs)))

    @commands.command()
    async def ignore(self, ctx, *, channel: discord.TextChannel = None):
        """ Stop doing anything here, or in the channel provided."""
        if ctx.guild.id not in self.bot.state.keys():
            return
        if not channel:
            channel = ctx.channel
        if channel.id in self.bot.state[ctx.guild.id]["listening_to"]:
            self.bot.state[ctx.guild.id]["listening_to"].remove(channel.id)
        if channel.id in self.bot.state[ctx.guild.id]["announcing_in"]:
            self.bot.state[ctx.guild.id]["announcing_in"].remove(channel.id)
        song_logger.info(
            f"dropped channel {channel.id} in guild {ctx.guild.id}")
        await ctx.send(f"No longer using <#{channel.id}> for anything.")

    ###
    # insert recommendations into the database periodically
    ###
    @tasks.loop(minutes=5.0)
    async def songs_db_inserter(self):
        async with self.dblock:
            song_logger.info("automatically inserting songs into database")
            await self.insert_song_recommendations()

    async def insert_song_recommendations(self):
        if len(self.songs) > 0:
            song_logger.info(
                f"inserting {len(self.songs)} new reccomendations into the database")
            async with self.bot.dbengine.begin() as conn:
                await conn.execute(sqla.insert(self.bot.recs_table, self.songs))
            self.songs.clear()

    @songs_db_inserter.after_loop
    async def on_insert_cancel(self):
        if self.songs_db_inserter.is_being_cancelled() and len(self.songs) > 0:
            async with self.dblock:
                song_logger.info(
                    f"inserting remaining {len(self.songs)} reccomendations into the database")
                await self.insert_song_recommendations()


def setup(bot):
    song_logger.info("setting up song saving extension")
    bot.add_cog(SongSavingCog(bot))


def teardown(bot):
    song_logger.info("tearing down song saving extension")
    bot.remove_cog('Song Saving')
