import sqlite3


DATABASE = "playdex.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_table():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL
        )
    """)

    connection.execute("""
        PRAGMA table_info(users)
    """)

    columns = [row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()]

    if "profile_message" not in columns:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN profile_message TEXT NOT NULL
            DEFAULT 'My games. My ratings. My reviews.'
        """)


    connection.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            platform TEXT,
            rating REAL NOT NULL,
            review TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS about_page (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            title TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    existing_about = connection.execute("""
        SELECT id
        FROM about_page
        WHERE id = 1
    """).fetchone()

    if existing_about is None:
        connection.execute("""
            INSERT INTO about_page (id, title, content)
            VALUES (?, ?, ?)
        """, (
            1,
            "About Playdex",
            """Playdex is a personal game tracking and review app.

    It lets you keep track of the games you've played, rate them, and write your own reviews.

    I made Playdex as a way to combine my interest in gaming with my interest in programming."""
        ))

    connection.execute("""
        CREATE TABLE IF NOT EXISTS site_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            footer_content TEXT NOT NULL
        )
    """)

    existing_footer = connection.execute("""
        SELECT id
        FROM site_settings
        WHERE id = 1
    """).fetchone()

    if existing_footer is None:
        connection.execute("""
            INSERT INTO site_settings (id, footer_content)
            VALUES (?, ?)
        """, (
            1,
            "© 2026 Playdex\nMade by jc21"
    ))

    connection.execute("""
        CREATE TABLE IF NOT EXISTS version_history (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            content TEXT NOT NULL
        )
    """)

    existing_version_history = connection.execute("""
        SELECT id
        FROM version_history
        WHERE id = 1
    """).fetchone()

    if existing_version_history is None:
        connection.execute("""
            INSERT INTO version_history (id, content)
            VALUES (?, ?)
        """, (
            1,
            """Playdex Version History

Version 1.0
- Playdex launched.
"""
        ))



    # Add user_id to older Playdex databases that do not have it yet.
    columns = connection.execute("PRAGMA table_info(games)").fetchall()

    column_names = [column["name"] for column in columns]

    if "user_id" not in column_names:
        connection.execute("""
            ALTER TABLE games
            ADD COLUMN user_id INTEGER
        """)

    connection.commit()
    connection.close()