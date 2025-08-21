from os import getenv
from warnings import warn

from dotenv import load_dotenv
load_dotenv()

POSTGRES_CONNECTION_URI: str = getenv("POSTGRES_CONNECTION_URI")

TOKEN: str = getenv("TOKEN")
DEFAULT_PREFIX: str = getenv("DEFAULT_PREFIX")

OWNER_IDS = ()  # comma-separated list (123,456,789)
if ids := getenv("OWNER_IDS"):
    OWNER_IDS = tuple(int(id) for id in ids.split(","))

JEYY_API = getenv("JEYY_API")
TOP_GG = getenv("TOP_GG")
DBL = getenv("DBL")

ANILIST_ID = getenv("ANILIST_ID")
ANILIST_SECRET = getenv("ANILIST_SECRET")
ANILIST_URL = (
    "https://anilist.co/api/v2/oauth/authorize"
    f"?client_id={ANILIST_ID}"
    "&redirect_uri=https://anilist.co/api/v2/oauth/pin"
    "&response_type=code"
)
ANILIST_REDIRECT = getenv("ANILIST_REDIRECT")

assert TOKEN
assert DEFAULT_PREFIX
assert POSTGRES_CONNECTION_URI

if None in (ANILIST_ID, ANILIST_SECRET):
    warn("AniList ID or secret is not present in config, using AniList OAuth services won't be possible.", stacklevel=1)

del getenv, warn
