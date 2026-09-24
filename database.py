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
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            platform TEXT,
            rating REAL NOT NULL,
            review TEXT
        )
    """)

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