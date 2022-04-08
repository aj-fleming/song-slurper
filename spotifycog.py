from datetime import datetime, timezone
import json
import os
import pandas as pd
import sqlalchemy as sqla


import discord
import spotipy
from discord.ext import commands, tasks
from spotipy.oauth2 import SpotifyClientCredentials

from utils import SongRecMeta, SpotifyURI, is_track, is_valid_spotify_uri

_STATE_DIR = "slurper_state"
_SPOTIFY_STATE_FILENAME = "spotify.json"
_SPOTIFY_STATE = os.path.join(_STATE_DIR, _SPOTIFY_STATE_FILENAME)
_RECS_DB = "recommendations.db"


def rec_meta_by_week(week):
    """ Generates the file path to a given week's recommendation metadata"""
    return os.path.join(_STATE_DIR, "recommendations_meta.{0}.{1}.json".format(*week))


def which_week():
    """ return the current year and week as a 2-tuple of ints"""
    utc_now = datetime.now(tz=timezone.utc)
    this_week = utc_now.isocalendar()[:2]
    return this_week


class SpotifyCog(commands.Cog, name="Spotify"):
    def __init__(self, bot):
        # set up clean state
        self.bot = bot
        # these get set later
        # we hope!
        self.dbengine = None
        self.dbmeta = None
        self.recs_table = None

        self.listening_in = set()  # channel IDs to get spotify links from
        self.recs_at = set()  # channel IDs to post playlist links to

        # load channel ids
        # TODO save (guild, channel) pairs for less discord api calls
        if os.path.isfile("slurper_state/spotify.json"):
            self.load_previous_state()

        # songs: list of dicts matching the recommendations table schema
        self.songs = []

    def load_previous_state(self):
        print("Loading previous spotify cog state...")
        with open(_SPOTIFY_STATE) as statefile:
            state = json.load(statefile)
        for id in state["listening_in"]:
            self.listening_in.add(id)
        for id in state["recs_at"]:
            self.recs_at.add(id)

    def cog_unload(self):
        print("Saving Spotify cog state...")
        state = {"listening_in": list(self.listening_in),
                 "recs_at": list(self.recs_at)}
        with open(_SPOTIFY_STATE, 'w+') as statefile:
            json.dump(state, statefile)
        if len(self.songs) > 0:
            with self.dbengine.begin() as conn:
                conn.execute(sqla.insert(self.recs_table, self.songs))

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.channel.id not in self.listening_in:
            return
        if msg.author.id == self.bot.user.id:
            return
        if len(msg.embeds) > 0:
            spotify_uris = filter(is_valid_spotify_uri, [
                                  SpotifyURI.from_link(e.url) for e in msg.embeds])
            tracks = list(filter(is_track, spotify_uris))

            tstamp = pd.Timestamp.utcnow().isoformat()
            for t in tracks:
                self.songs.append({"resource_type": t.resource_type,
                                   "uri": t.identifier,
                                   "guild": msg.guild.id,
                                   "channel": msg.channel.id,
                                   "user": msg.author.id,
                                   "timestamp": tstamp})

    @commands.command()
    async def slurp(self, ctx, *, channel: discord.TextChannel = None):
        """ Listen for song suggestions here, or in the provided channel."""
        if not channel:
            channel = ctx.channel
        self.listening_in.add(channel.id)
        await channel.send(f"I am now listening to recommendations in <#{channel.id}>")

    @commands.command()
    async def announce(self, ctx, *, channel: discord.TextChannel = None):
        """ Announce playlist suggestions here, or in the provided channel."""
        if not channel:
            channel = ctx.channel
        self.recs_at.add(channel.id)
        await channel.send(f"I am now announcing my playlists in <#{channel.id}>")

    @commands.command()
    async def channels(self, ctx):
        """ Shows the channels used in this server. """
        guild_listen = filter(lambda c: self.bot.get_channel(
            c).guild.id == ctx.guild.id, self.listening_in)
        guild_recs = filter(lambda c: self.bot.get_channel(
            c).guild.id == ctx.guild.id, self.recs_at)
        l_refs = ["<#{0}>".format(c) for c in guild_listen]
        r_refs = ["<#{0}>".format(c) for c in guild_recs]
        await ctx.send("I am listening for recommendations in {0}. I am announcing playlists in {1}.".format(", ".join(l_refs), ", ".join(r_refs)))

    @commands.command()
    async def stop(self, ctx, *, channel: discord.TextChannel = None):
        """ Stop doing anything here, or in the channel provided."""
        if not channel:
            channel = ctx.channel
        if channel.id in self.listening_in:
            self.listening_in.remove(channel.id)
        if channel.id in self.recs_at:
            self.recs_at.remove(channel.id)
        await ctx.send(f"No longer using <#{channel.id}> for anything.")


def setup(bot):
    print("Loading Spotify cog!")
    bot.add_cog(SpotifyCog(bot))
    print("Spotify cog loaded.")


def teardown(bot):
    print("Unloading Spotify cog!")
    bot.remove_cog('Spotify')
    print("Spotify cog unloaded.")
