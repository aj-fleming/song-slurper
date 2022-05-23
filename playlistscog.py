import asyncio
from curses import window
import json
import logging
import os

import discord
from discord.ext import commands, tasks
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sqlalchemy as sqla
from sqlalchemy import select, and_

from helpers import SpotifyURI, CacheDirectoryHandler, run_at

pl_logger = logging.getLogger('songbot.playlists')

sp_scopes = ("playlist-modify-public", "user-library-read")


class PlaylistManagementCog(commands.Cog, name="Playlist Management"):
    def __init__(self, bot):
        self.bot = bot
        self.creation_task = self.bot.loop.create_task(self.make_weekly_playlists())

    def cog_unload(self):
        self.creation_task.cancel()

    async def make_weekly_playlists(self):
        now = pd.Timestamp.utcnow().tz_localize(tz=None)
        yr, wk, _ = now.isocalendar()
        next_friday_noon = pd.Timestamp.fromisocalendar(
            yr, wk, 5) + pd.Timedelta(.5, unit='days')
        # if this week's friday has already happened, then the next friday must be next week
        if next_friday_noon < now:
            next_friday_noon += pd.Timedelta(7, unit='days')

        pl_logger.info(f"waiting until {next_friday_noon} to create playlists")
        await run_at(self.create_spotify_lists(next_friday_noon), next_friday_noon)

        pl_logger.info(f"submitting weekly playlists tasks to bot event loop")
        self.creation_task = self.bot.loop.create_task(self.make_weekly_playlists())

    async def create_spotify_lists(self, end_dt, window_width=pd.Timedelta(7, unit="days")):
        start_dt = end_dt - window_width
        # alias this for ease-of-use
        recs_table = self.bot.recs_table
        for guild_id in self.bot.state.keys():
            query = select(recs_table).where(recs_table.c.guild == guild_id,
                                             recs_table.c.timestamp >= start_dt,
                                             recs_table.c.timestamp <= end_dt)
            async with self.bot.dbengine.begin() as conn:
                results = await conn.execute(query)
            songs_df = pd.DataFrame(results.fetch_all()).set_index("id")


def setup(bot):
    pl_logger.info("setting up playlist extension")
    bot.add_cog(PlaylistManagementCog(bot))


def teardown(bot):
    pl_logger.info("tearing down playlist extension")
    bot.remove_cog('Playlist Management')
