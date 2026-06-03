CREATE TABLE IF NOT EXISTS users (
    vk_id INTEGER PRIMARY KEY,
    age INTEGER,
    consent_given BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_sessions (
    id SERIAL PRIMARY KEY,
    vk_id INTEGER REFERENCES users(vk_id) ON DELETE CASCADE,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    wilson_result INTEGER NOT NULL,
    ecmes_result INTEGER NOT NULL,
    luria_result INTEGER NOT NULL,
    schulte_time_result DECIMAL NOT NULL,
    schulte_errors_result INTEGER NOT NULL,
    raven_time_result DECIMAL NOT NULL,
    raven_errors_result INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS word_bank (
    id SERIAL PRIMARY KEY,
    word VARCHAR(50) UNIQUE NOT NULL,
    difficulty INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raven_tests (
    id SERIAL PRIMARY KEY,
    image VARCHAR(50) UNIQUE NOT NULL,
    answer INTEGER NOT NULL,
    answers_count INTEGER NOT NULL,
    category VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_test_sessions_vk_id ON test_sessions(vk_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_date ON test_sessions(date);
CREATE INDEX IF NOT EXISTS idx_raven_tests_category ON raven_tests(category);

INSERT INTO word_bank (word, difficulty) VALUES
    ('дом', 1), ('лес', 1), ('кот', 1), ('стол', 1), ('книга', 1),
    ('машина', 1), ('река', 1), ('солнце', 1), ('цветок', 1), ('птица', 1),
    ('молоко', 1), ('хлеб', 1), ('рука', 1), ('нога', 1), ('глаз', 1),
    ('вода', 1), ('огонь', 1), ('земля', 1), ('небо', 1), ('звезда', 1),
    ('друг', 1), ('мама', 1), ('папа', 1), ('брат', 1), ('сестра', 1),
    ('школа', 1), ('работа', 1), ('город', 1), ('улица', 1), ('парк', 1),
    ('счастье', 2), ('успех', 2), ('мечта', 2), ('будущее', 2), ('знание', 2),
    ('творчество', 2), ('развитие', 2), ('гармония', 2), ('свобода', 2), ('мудрость', 2)
ON CONFLICT (word) DO NOTHING;