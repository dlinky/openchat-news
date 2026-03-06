-- ChatDigest 데이터베이스 스키마
-- PostgreSQL 16+

CREATE TABLE IF NOT EXISTS chat_rooms (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    tags        TEXT[]       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           SERIAL PRIMARY KEY,
    room_id      INTEGER      NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    sender       VARCHAR(255),
    content      TEXT,
    message_type VARCHAR(20)  NOT NULL DEFAULT 'text',  -- text / image / emoticon / system
    sent_at      TIMESTAMPTZ  NOT NULL,
    chat_date    DATE         NOT NULL,                  -- 새벽 4시 기준 날짜
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_room_date ON chat_messages(room_id, chat_date);
CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_date  ON chat_messages(chat_date);

CREATE TABLE IF NOT EXISTS daily_summaries (
    id         SERIAL PRIMARY KEY,
    room_id    INTEGER     NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    date       DATE        NOT NULL,
    summary_md TEXT,
    topics     TEXT[]      NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (room_id, date)
);

CREATE TABLE IF NOT EXISTS daily_digests (
    id         SERIAL PRIMARY KEY,
    date       DATE        NOT NULL UNIQUE,
    content_md TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekly_digests (
    id         SERIAL PRIMARY KEY,
    year       INTEGER     NOT NULL,
    week       INTEGER     NOT NULL,
    content_md TEXT,
    date_from  DATE        NOT NULL,
    date_to    DATE        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (year, week)
);

CREATE TABLE IF NOT EXISTS monthly_digests (
    id         SERIAL PRIMARY KEY,
    year       INTEGER     NOT NULL,
    month      INTEGER     NOT NULL,
    content_md TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (year, month)
);
