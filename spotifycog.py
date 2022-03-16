import json
import os
import time
import string
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

import discord
from discord.ext import commands, tasks


class SpotifyURI:
    def __init__(self, resource_type, id):
        self.resource_type = resource_type
        self.id = id

    def __str__(self) -> str:
        return "spotify:{0}:{1}".format(self.resource_type, self.id)

    def __eq__(self, __o: object) -> bool:
        return (__o.id == self.id) if isinstance(__o, SpotifyURI) else False


def is_valid_spotify_uri(uri):
    return uri.resource_type is not None and uri.id is not None


def is_track(uri):
    return uri.resource_type == "track"


def is_album(uri):
    return uri.resource_type == "album"


def is_playlist(uri):
    return uri.resource_type == "playlist"


def is_user(uri):
    return uri.resource_type == "user"


def is_artist(uri):
    return uri.resource_type == "artist"


def extract_spotify_uri(spotify_link: str) -> SpotifyURI:
    s = spotify_link.strip().split("/")
    if "open.spotify.com" not in s:
        return SpotifyURI(None, None)
    # we have a spotify link, remove any GET parameters from the last bit
    # and fuse everything back together
    uri = SpotifyURI(s[-2], s[-1].split("&")[0])
    return uri


class SpotifyCog(commands.Cog, name="Spotify"):
    def __init__(self, bot):
        self.bot = bot
        self.listening_in = set()
        self.recs_at = set()
        if os.path.isfile("slurper_state/spotify.json"):
            self.load_previous_state()
        print("Connecting to Spotify...")
        auth = SpotifyClientCredentials()
        self.spotify = spotipy.Spotify(auth_manager=auth)
        print("Spotify cog ready!")

    def load_previous_state(self):
        print("Loading previous spotify cog state...")
        with open("slurper_state/spotify.json") as statefile:
            state = json.load(statefile)
        for id in state["listening_in"]:
            self.listening_in.add(id)
        for id in state["recs_at"]:
            self.recs_at.add(id)

    def cog_unload(self):
        print("Saving Spotify cog state...")
        state = {"listening_in": list(self.listening_in),
                 "recs_at": list(self.recs_at)}
        with open("slurper_state/spotify.json", 'w+') as statefile:
            json.dump(state, statefile)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.channel.id not in self.listening_in:
            return
        if msg.author.id == self.bot.user.id:
            return
        if len(msg.embeds) > 0:
            spotify_uris = filter(is_valid_spotify_uri, [
                                  extract_spotify_uri(e.url) for e in msg.embeds])
            tracks = list(filter(is_track, spotify_uris))
            for t in tracks:
                print(t)

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
    async def stop(self, ctx, *, channel:discord.TextChannel=None):
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
