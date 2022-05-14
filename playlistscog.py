import asyncio
import json
import logging
import os

import discord
from discord.ext import commands, tasks
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sqlalchemy as sqla

from helpers import SpotifyURI, CacheDirectoryHandler, run_at

pl_logger = logging.getLogger('songbot.playlists')


class PlaylistManagementCog(commands.Cog, name="Playlist Management"):
    def __init__(self, bot):
        self.bot = bot

    async def make_weekly_playlists(self):
        now = pd.Timestamp.utcnow()
        until_friday_noon = pd.Timedelta(
            (4-now.isoweekday()) % 7 + 1, unit='days') + pd.Timedelta(12, unit='hours')
        pl_logger.info(f"waiting until {now+until_friday_noon} to create playlists")
        await run_at(self.create_spotify_lists(), now+until_friday_noon)

        pl_logger.info(f"submitting weekly playlists tasks to bot event loop")
        self.bot.loop.create_task(self.make_weekly_playlists())

    async def create_spotify_lists(self):
        pass


def setup(bot):
    pl_logger.info("setting up playlist extension")
    bot.add_cog(PlaylistManagementCog(bot))


def teardown(bot):
    pl_logger.info("tearing down playlist extension")
    bot.remove_cog('Playlist Management')
