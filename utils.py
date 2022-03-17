from dataclasses import dataclass


class SpotifyURI:
    def __init__(self, resource_type, id):
        self.resource_type = resource_type
        self.id = id

    def __str__(self) -> str:
        return "spotify:{0}:{1}".format(self.resource_type, self.id)

    def __eq__(self, __o: object) -> bool:
        return (__o.id == self.id) if isinstance(__o, SpotifyURI) else False

    def __hash__(self):
        return hash(self.id)

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
        return {"resource_type": self.resource_type, "id": self.id}


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