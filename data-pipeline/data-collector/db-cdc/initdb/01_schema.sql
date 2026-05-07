CREATE TABLE IF NOT EXISTS user_profile (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(128) NOT NULL,
    city VARCHAR(64),
    tags TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO user_profile (user_name, city, tags)
VALUES
    ('alice', 'shanghai', 'graduate,recommendation'),
    ('bob', 'beijing', 'backend,java')
ON CONFLICT DO NOTHING;
