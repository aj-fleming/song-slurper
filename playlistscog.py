import asyncio
import json
import logging
import os

import discord
from discord.ext import commands, tasks

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sqlalchemy as sqla

from helpers import SpotifyURI, CacheDirectoryHandler

pl_logger = logging.getLogger('songbot.playlists')

class PlaylistManagementCog(commands.Cog, name="Playlist Management"):
    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    pl_logger.info("setting up playlist extension")
    bot.add_cog(PlaylistManagementCog(bot))

def teardown(bot):
    pl_logger.info("tearing down playlist management")
    bot.remove_cog('Playlist Management')