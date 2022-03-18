import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
import spotipy
from discord.ext import commands, tasks
from spotipy.oauth2 import SpotifyClientCredentials

from utils import SongRecMeta, SpotifyURI, is_track, is_valid_spotify_uri

_STATE_DIR = "slurper_state"
_SPOTIFY_STATE_FILENAME = "spotify.json"
_SPOTIFY_STATE = os.path.join(_STATE_DIR, _SPOTIFY_STATE_FILENAME)

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
        self.listening_in = set()  # channel IDs to get spotify links from
        self.recs_at = set()  # channel IDs to post playlist links to

        if os.path.isfile("slurper_state/spotify.json"):
            self.load_previous_state()

        # songs: dict from (year, week) -> SongRecMeta struct
        self.songs = dict()
        this_week = which_week()
        self.songs.update({this_week: set()})
        playlist_files = os.listdir(_STATE_DIR)
        this_weeks_plf = rec_meta_by_week(this_week)
        if this_weeks_plf in playlist_files:
            with open(os.path.join(_STATE_DIR, this_weeks_plf)) as plf:
                # should be a list of dicts
                try:
                    recs = json.load(plf)
                    for rec in recs:
                        self.songs[this_week].add(SongRecMeta.from_dict(rec))
                except(json.JSONDecodeError):
                    print("tried to load bad playlist json")

    
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

        loaded_weeks = self.songs.keys()
        for wk in loaded_weeks:
            print(wk)
            wk_plf = rec_meta_by_week(wk)
            with open("slurper_state/{0}".format(wk_plf), "w+") as out:
                json.dump([s.to_dict() for s in self.songs[wk]], out)

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
            wk = self.which_week()
            for t in tracks:
                self.songs[wk].add(SongRecMeta(
                    t, msg.author.id, msg.guild.id))

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
