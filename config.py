from os import getenv
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

OWNER_IDS = ()  # comma-separated list (123,456,789)
if ids := getenv("OWNER_IDS"):
    OWNER_IDS = tuple(int(id) for id in ids.split(","))

print(OWNER_IDS)

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
