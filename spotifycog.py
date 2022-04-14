import json
import os
from datetime import datetime, timezone

import discord
import pandas as pd
from requests import JSONDecodeError
import spotipy
import sqlalchemy as sqla
from discord.ext import commands, tasks
from spotipy.oauth2 import SpotifyOAuth

from helpers import SpotifyURI, is_track, is_valid_spotify_uri

_SPOTIFY_SCOPES = ("user-library-read", "playlist-modify-public")


_STATE_DIR = "slurper_state"
_SPOTIFY_STATE_FILENAME = "spotify.json"
_SPOTIFY_STATE = os.path.join(_STATE_DIR, _SPOTIFY_STATE_FILENAME)
_RECS_DB = "recommendations.db"


class SpotifyCog(commands.Cog, name="Spotify"):
    def __init__(self, bot):
        # set up clean state
        self.bot = bot
        self.state = {}

        # these get set later via forward_dbengine()
        # (we hope)
        self.dbengine = None
        self.dbmeta = None
        self.recs_table = None

        # load previous state
        if os.path.isfile("slurper_state/spotify.json"):
            try:
                self.state = self.load_previous_state()
            except JSONDecodeError:
                print("could not parse previous state, resetting")
                pass

        # songs: list of dicts matching the recommendations table schema
        self.songs = []

    def load_previous_state(self):
        print("Loading previous spotify cog state...")
        with open(_SPOTIFY_STATE) as statefile:
            old_state = json.load(statefile)
        new_state = {}
        for guild_id, infos in old_state.items():
            announcer = infos["announcer"]
            for k in announcer.keys():
                if not announcer[k]:
                    announcer[k] = 0
            new_state[guild_id] = {
                "announcer": {
                    "discord_id": announcer["discord_id"],
                    "sp_user": announcer["sp_user"]
                },
                "listening_to": set(infos["listening_to"]),
                "announcing_in": set(infos["announcing_in"])
            }
        return new_state

    def cog_unload(self):
        print("Saving Spotify cog state...")
        with open(_SPOTIFY_STATE, 'w+') as statefile:
            json.dump(self.state, statefile, default=list)
        if len(self.songs) > 0:
            with self.dbengine.begin() as conn:
                conn.execute(sqla.insert(self.recs_table, self.songs))

    def add_new_guild(self, new_id):
        self.state.update({new_id: {"announcer": {"discord_id": 0, "sp_user": 0},
                                    "listening_to": set(), "announcing_in": set()}})

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.id == self.bot.user.id:
            return
        if msg.guild.id in self.state:
            if msg.channel.id not in self.state[msg.guild.id]["listening_to"]:
                return
            if len(msg.embeds) > 0:
                spotify_uris = filter(is_valid_spotify_uri, [
                    SpotifyURI.from_link(e.url) for e in msg.embeds])
                tracks = filter(is_track, spotify_uris)
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

        if ctx.guild.id not in self.state.keys():
            self.add_new_guild(ctx.guild.id)

        if not channel:
            channel = ctx.channel
        self.state[ctx.guild.id]["listening_to"].add(channel.id)
        await channel.send(f"I am now listening to recommendations in <#{channel.id}>")

    @commands.command()
    async def announce(self, ctx, *, channel: discord.TextChannel = None):
        """ Announce playlist suggestions here, or in the provided channel."""

        if ctx.guild.id not in self.state.keys():
            self.add_new_guild(ctx.guild.id)

        if not channel:
            channel = ctx.channel
        self.state[ctx.guild.id]["announcing_in"].add(channel.id)
        await channel.send(f"I am now announcing my playlists in <#{channel.id}>")

    @commands.command()
    async def channels(self, ctx):
        """ Shows the channels used in this server. """
        if ctx.guild.id not in self.state.keys():
            await ctx.send("I am not configured to do anything in this server yet!")
        else:
            l_refs = ["<#{0}>".format(
                c) for c in self.state[ctx.guild.id]["listening_to"]]
            r_refs = ["<#{0}>".format(
                c) for c in self.state[ctx.guild.id]["announcing_in"]]
            await ctx.send("I am listening for recommendations in {0}. I am announcing playlists in {1}.".format(", ".join(l_refs), ", ".join(r_refs)))

    @commands.command()
    async def stop(self, ctx, *, channel: discord.TextChannel = None):
        """ Stop doing anything here, or in the channel provided."""
        if ctx.guild.id not in self.state.keys():
            return
        if not channel:
            channel = ctx.channel
        if channel.id in self.state[ctx.guild.id]["listening_to"]:
            self.state[ctx.guild.id]["listening_to"].remove(channel.id)
        if channel.id in self.state[ctx.guild.id]["announcing_in"]:
            self.state[ctx.guild.id]["announcing_in"].remove(channel.id)
        await ctx.send(f"No longer using <#{channel.id}> for anything.")


def setup(bot):
    print("Loading Spotify cog!")
    bot.add_cog(SpotifyCog(bot))
    print("Spotify cog loaded.")


def teardown(bot):
    print("Unloading Spotify cog!")
    bot.remove_cog('Spotify')
    print("Spotify cog unloaded.")
