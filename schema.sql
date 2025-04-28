BEGIN;

CREATE TABLE IF NOT EXISTS prefixes(
    guild_id BIGINT PRIMARY KEY,
    prefixes VARCHAR(5)[] NOT NULL
);

CREATE INDEX IF NOT EXISTS prefixes_guild_id_idx ON prefixes (guild_id);
CREATE INDEX IF NOT EXISTS prefixes_prefix_idx ON prefixes (prefixes);

CREATE TABLE IF NOT EXISTS command_statistics(
    guild_id BIGINT PRIMARY KEY,
    count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS message_statistics(
    guild_id BIGINT,
    user_id BIGINT,
    count INTEGER DEFAULT 0,
    bot BOOLEAN,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS blacklist(
    user_id BIGINT PRIMARY KEY,
    guild_ids BIGINT[],
    global boolean NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS guild_blacklist(
    guild_id BIGINT PRIMARY KEY,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT current_timestamp
);

/* CREATE TABLE IF NOT EXISTS anilist_tokens(
    user_id BIGINT PRIMARY KEY,
    token TEXT NOT NULL,
    refresh TEXT NOT NULL,
    expiry TIMESTAMP NOT NULL
); */

CREATE TABLE IF NOT EXISTS anilist_tokens_new(
    user_id BIGINT PRIMARY KEY,
    token BYTEA NOT NULL,
    refresh TEXT NOT NULL,
    expiry TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS logging_config(
    guild_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL,
    channel_id BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS logging_events(
    guild_id BIGINT REFERENCES logging_config(guild_id),
    message_delete BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS inline_search_optout(
    user_id BIGINT
);

CREATE TABLE IF NOT EXISTS error_reports(
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    message_content TEXT NOT NULL,
    author_id BIGINT NOT NULL,
    traceback TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT current_timestamp,
    status BOOLEAN
);

CREATE TABLE IF NOT EXISTS afk(
    user_id BIGINT PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT current_timestamp,
    reason TEXT
);

COMMIT;