from dataclasses import dataclass
import os

from spotipy import CacheFileHandler

# handle directory of cache files for different Spotify usernames
class CacheDirectoryHandler(CacheFileHandler):
    """
    Class to handle the creation and naming of token cache files for spotipy
    """
    def __init__(self, cache_directory, username):
        if not os.path.isdir(cache_directory):
            os.mkdir(cache_directory)
        self.cache_path = f"{cache_directory}/.token-cache-{username}"

class SpotifyURI:
    def __init__(self, resource_type, id):
        self.resource_type = resource_type
        self.identifier = id

    def __str__(self) -> str:
        return "spotify:{0}:{1}".format(self.resource_type, self.identifier)

    def __eq__(self, __o: object) -> bool:
        return (__o.identifier == self.identifier) if isinstance(__o, SpotifyURI) else False

    def __hash__(self):
        return hash(self.identifier)

    @classmethod
    def from_dict(cls, s: dict):
        return cls(s["resource_type"], s["id"])

    @classmethod
    def from_link(cls, url: str):
        s = url.strip().split("/")
        if "open.spotify.com" not in s:
            return cls(None, None)
        # we have a spotify link, remove any GET parameters from the last bit
        # and fuse everything back together
        uri = cls(s[-2], s[-1].split("&")[0])
        return uri

    def to_dict(self) -> dict:
        return {"resource_type": self.resource_type, "id": self.identifier}


def is_valid_spotify_uri(uri):
    return uri.resource_type is not None and uri.identifier is not None


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


@dataclass
class SongRecMeta:
    """ Data class for keeping track of song suggestions. """
    track: SpotifyURI
    user_id: int
    guild_id: int

    def __hash__(self):
        return hash((self.track, self.user_id, self.guild_id))

    @classmethod
    def from_dict(cls, d: dict):
        return cls(SpotifyURI.from_dict(d["track"]), d["user_id"], d["guild_id"])

    def to_dict(self) -> dict:
        return {"track": self.track.to_dict(), "user_id": self.user_id, "guild_id": self.guild_id}
