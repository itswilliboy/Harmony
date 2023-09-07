BEGIN;

CREATE TABLE IF NOT EXISTS prefixes(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(5) NOT NULL
);

CREATE TABLE IF NOT EXISTS statistics(
    guild_id BIGINT PRIMARY KEY,
    command_runs INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blacklist(
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    user_id BIGINT NOT NULL,
    reason TEXT DEFAULT 'No reason given.'
);

COMMIT;