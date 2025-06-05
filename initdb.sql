\c cycleparks;
DROP TABLE IF EXISTS requests;
DROP TABLE IF EXISTS command_stats;

CREATE TABLE requests (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    user_id BIGINT NOT NULL,
    command TEXT NOT NULL
);

CREATE TABLE command_stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    command TEXT NOT NULL,
    count INTEGER NOT NULL
);

CREATE TABLE send_failures (
    id SERIAL PRIMARY KEY,
    message_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    count INTEGER NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);