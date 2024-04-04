BEGIN;

CREATE TABLE IF NOT EXISTS prefixes(
    guild_id BIGINT PRIMARY KEY,
    prefixes VARCHAR(5)[] NOT NULL
);

CREATE INDEX IF NOT EXISTS prefixes_guild_id_idx ON prefixes (guild_id);
CREATE INDEX IF NOT EXISTS prefixes_prefix_idx ON prefixes (prefixes);

CREATE TABLE IF NOT EXISTS statistics(
    guild_id BIGINT PRIMARY KEY,
    command_runs INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blacklist(
    user_id BIGINT PRIMARY KEY,
    guild_ids BIGINT[],
    global boolean NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_blacklist(
    guild_id BIGINT PRIMARY KEY,
    reason TEXT,
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS snipe_optout(
    user_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS avatar_history(
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    image_data BYTEA,
    timestamp TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS anilist_codes(
    user_id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,
    expires_in TIMESTAMP NOT NULL
);

COMMIT;