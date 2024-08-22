from os import getenv
from re import compile
from warnings import warn

POSTGRES_CREDENTIALS = {
    "user": getenv("POSTGRES_USER"),
    "password": getenv("POSTGRES_PASSWORD"),
    "database": getenv("POSTGRES_DATABASE"),
    "host": getenv("POSTGRES_HOST"),
    "port": getenv("POSTGRES_PORT"),
}

TOKEN: str = getenv("TOKEN")
DEFAULT_PREFIX: str = getenv("DEFAULT_PREFIX")

OWNER_IDS = ()
pattern = compile(r"(.+?)(?:,|$)")  # comma-separated list
if ids := getenv("OWNER_IDS"):
    matches = pattern.findall(ids)

    OWNER_IDS = tuple(int(i) for i in matches)

JEYY_API = getenv("JEYY_API")

ANILIST_ID = getenv("ANILIST_ID")
ANILIST_SECRET = getenv("ANILIST_SECRET")
ANILIST_URL = (
    "https://anilist.co/api/v2/oauth/authorize"
    f"?client_id={ANILIST_ID}"
    "&redirect_uri=https://anilist.co/api/v2/oauth/pin"
    "&response_type=code"
)

if not all((i for i in POSTGRES_CREDENTIALS.values())):
    raise RuntimeError("Incomplete database credentials, connecting won't be possible.")

POSTGRES_CREDENTIALS: dict[str, str]

assert TOKEN
assert DEFAULT_PREFIX

if None in (ANILIST_ID, ANILIST_SECRET):
    warn("AniList ID or secret is not present in config, using AniList OAuth services won't be possible.")
