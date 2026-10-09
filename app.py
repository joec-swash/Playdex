import json
from urllib.parse import urlparse

import re

from markupsafe import Markup, escape

from functools import wraps
import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    abort
)

from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection, create_table

from markupsafe import Markup, escape

app = Flask(__name__)

app.config.from_pyfile("config.py")

app.config["9f88a5be0f6d8506646e81f648f19aa81acfcd24a18092a8dc6785ff399f16e3"] = os.environ.get(
    "9f88a5be0f6d8506646e81f648f19aa81acfcd24a18092a8dc6785ff399f16e3",
    app.config["SECRET_KEY"]
)

KEYWORD_LINKS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "keyword_links.json"
)


def load_keyword_links():
    try:
        with open(KEYWORD_LINKS_FILE, "r", encoding="utf-8") as file:
            links = json.load(file)

    except FileNotFoundError:
        return {}

    except (json.JSONDecodeError, OSError) as error:
        app.logger.error("Could not read keyword_links.json: %s", error)
        return {}

    if not isinstance(links, dict):
        return {}

    valid_links = {}

    for keyword, destination in links.items():
        if not isinstance(keyword, str) or not keyword.strip():
            continue

        if not isinstance(destination, str):
            continue

        destination = destination.strip()
        parsed_url = urlparse(destination)

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            continue

        valid_links[keyword.strip().casefold()] = destination

    return valid_links


@app.context_processor
def inject_keyword_link_keywords():
    return {
        "keyword_link_keywords": list(load_keyword_links().keys())
    }


PLATFORM_GROUPS = {
    "PlayStation": [
        "PlayStation 5 Pro",
        "PlayStation 5",
        "PlayStation 4 Pro",
        "PlayStation 4",
        "PlayStation 3",
        "PlayStation 2",
        "PlayStation",
        "PlayStation Vita",
        "PSP",
    ],
    "Xbox": [
        "Xbox Series X",
        "Xbox Series S",
        "Xbox One X",
        "Xbox One S",
        "Xbox One",
        "Xbox 360",
        "Xbox",
    ],
    "Nintendo": [
        "Switch 2",
        "Switch OLED",
        "Nintendo Switch",
        "Switch Lite",
        "Wii U",
        "Wii",
        "GameCube",
        "Nintendo 64",
        "SNES",
        "NES",
        "3DS",
        "2DS",
        "DS",
        "Game Boy Advance",
        "Game Boy Color",
        "Game Boy",
    ],
    "PC": [
        "Windows",
        "Mac",
        "Linux",
    ],
    "Steam Deck": [
        "Steam Deck",
    ],
    "Sega": [
        "Dreamcast",
        "Saturn",
        "Mega Drive / Genesis",
        "Master System",
        "Game Gear",
    ],
    "Atari": [
        "Atari 2600",
        "Atari 5200",
        "Atari 7800",
        "Atari Jaguar",
        "Atari Lynx",
    ],
    "Other": [
        "Other",
        "Unknown",
    ],
}


URL_PATTERN = re.compile(
    r'(?<![@\w])'
    r'('
        r'(?:https?://|www\.)[^\s<]+'
        r'|'
        r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s<]*)?'
    r')',
    re.IGNORECASE
)


@app.template_filter("linkify")
def linkify(value):
    if value is None:
        return ""

    text = str(value)
    output = []
    last_end = 0

    for match in URL_PATTERN.finditer(text):
        output.append(escape(text[last_end:match.start()]))

        raw_url = match.group(0)

        # Remove punctuation that belongs to the sentence, not the URL.
        url = raw_url
        trailing = ""

        while url and url[-1] in ".,!?;:)]}":
            trailing = url[-1] + trailing
            url = url[:-1]

        if url:
            href = url

            if not href.lower().startswith(("http://", "https://")):
                href = "https://" + href

            output.append(
                Markup('<a href="')
                + escape(href)
                + Markup('">')
                + escape(url)
                + Markup('</a>')
            )

            output.append(escape(trailing))

        last_end = match.end()

    output.append(escape(text[last_end:]))

    return Markup("").join(output)



create_table()


def login_required(route):
    @wraps(route)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        return route(*args, **kwargs)

    return wrapped

def admin_required(route):
    @wraps(route)
    def wrapped(*args, **kwargs):
        if session.get("username") != app.config.get("ADMIN_USERNAME"):
            return "You do not have permission to edit the About page.", 403

        return route(*args, **kwargs)

    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3:
            return render_template(
                "register.html",
                error="Username must be at least 3 characters long."
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters long."
            )

        connection = get_connection()

        existing_user = connection.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        if existing_user:
            connection.close()

            return render_template(
                "register.html",
                error="That username is already taken."
            )

        password_hash = generate_password_hash(password)

        cursor = connection.execute("""
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
        """, (username, password_hash))

        user_id = cursor.lastrowid

        # If Playdex already had games before accounts existed,
        # give those games to the first account created.
        connection.execute("""
            UPDATE games
            SET user_id = ?
            WHERE user_id IS NULL
        """, (user_id,))

        connection.commit()
        connection.close()

        session.clear()
        session["user_id"] = user_id
        session["username"] = username

        return redirect("/")

    return render_template("register.html")

@app.route("/keyword-link")
def keyword_link():
    keyword = request.args.get("keyword", "").strip().casefold()

    destination = load_keyword_links().get(keyword)

    if not destination:
        return redirect(url_for("home"))

    return redirect(destination, code=302)



@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        connection = get_connection()

        user = connection.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        connection.close()

        if user is None:
            return render_template(
                "login.html",
                error="Incorrect username or password."
            )

        if not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html",
                error="Incorrect username or password."
            )

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

@app.route("/about")
def about():
    connection = get_connection()

    about = connection.execute("""
        SELECT *
        FROM about_page
        WHERE id = 1
    """).fetchone()

    connection.close()

    is_admin = session.get("username") == app.config.get("ADMIN_USERNAME")

    return render_template(
        "about.html",
        about=about,
        is_admin=is_admin
    )

@app.route("/about/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_about():

    connection = get_connection()

    about = connection.execute("""
        SELECT *
        FROM about_page
        WHERE id = 1
    """).fetchone()

    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"]

        connection.execute("""
            UPDATE about_page
            SET title = ?,
                content = ?
            WHERE id = 1
        """, (title, content))

        connection.commit()
        connection.close()

        return redirect(url_for("about"))

    connection.close()

    return render_template(
        "edit_about.html",
        about=about
    )


@app.route("/")
def home():
    connection = get_connection()

    search = request.args.get("search", "").strip()
    platform_filter = request.args.get("platform_filter", "").strip()
    status_filter = request.args.get("status_filter", "").strip()
    achievement_filter = request.args.get("achievement_filter", "").strip()
    ownership_filter = request.args.get("ownership_filter", "").strip()
    min_rating_text = request.args.get("min_rating", "").strip()
    max_rating_text = request.args.get("max_rating", "").strip()

    sort_by = request.args.get("sort_by", "recent")

    sort_options = {
        "recent": ("id", "DESC"),
        "oldest": ("id", "ASC"),
        "title_az": ("title", "ASC"),
        "title_za": ("title", "DESC"),
        "rating_high": ("rating", "DESC"),
        "rating_low": ("rating", "ASC"),
        "hours_high": ("hours_played", "DESC"),
        "hours_low": ("hours_played", "ASC"),
        "times_high": ("times_played", "DESC"),
        "times_low": ("times_played", "ASC"),
    }

    if sort_by not in sort_options:
        sort_by = "recent"

    games = []
    profile_message = "My games. My ratings. My reviews."

    if session.get("user_id"):
        user = connection.execute("""
            SELECT id, profile_message
            FROM users
            WHERE id = ?
        """, (session["user_id"],)).fetchone()

        if user:
            profile_message = (
                user["profile_message"]
                or "My games. My ratings. My reviews."
            )

            conditions = ["user_id = ?"]
            parameters = [user["id"]]

            # Search game titles.
            if search:
                conditions.append("title LIKE ?")
                parameters.append(f"%{search}%")

            # Filter by platform. Supports games saved with two platforms.
            if platform_filter:
                conditions.append("""
                    (',' || REPLACE(
                        COALESCE(platform, ''),
                        ', ',
                        ','
                    ) || ',') LIKE ?
                """)
                parameters.append(f"%,{platform_filter},%")

            # Filter by status.
            if status_filter in {
                "Completed",
                "Playing",
                "Did not finish"
            }:
                conditions.append("status = ?")
                parameters.append(status_filter)

            # Filter by Platinum / all achievements.
            if achievement_filter in {"Yes", "No"}:
                conditions.append("achievements_complete = ?")
                parameters.append(achievement_filter)

            # Filter by physical or digital.
            if ownership_filter in {"Physical", "Digital"}:
                conditions.append("ownership_type = ?")
                parameters.append(ownership_filter)

            # Filter by minimum rating.
            try:
                min_rating = float(min_rating_text)

                if 0 <= min_rating <= 10:
                    conditions.append("rating >= ?")
                    parameters.append(min_rating)

            except ValueError:
                pass

            # Filter by maximum rating.
            try:
                max_rating = float(max_rating_text)

                if 0 <= max_rating <= 10:
                    conditions.append("rating <= ?")
                    parameters.append(max_rating)

            except ValueError:
                pass

            sort_column, sort_direction = sort_options[sort_by]

            # Put games without recorded hours/times at the end.
            if sort_column in {"hours_played", "times_played"}:
                order_clause = (
                    f"CASE WHEN {sort_column} IS NULL "
                    f"THEN 1 ELSE 0 END ASC, "
                    f"{sort_column} {sort_direction}, id DESC"
                )
            else:
                order_clause = f"{sort_column} {sort_direction}, id DESC"

            query = f"""
                SELECT *
                FROM games
                WHERE {" AND ".join(conditions)}
                ORDER BY {order_clause}
            """

            games = connection.execute(
                query,
                parameters
            ).fetchall()

    connection.close()

    platform_options = sorted({
        console
        for consoles in PLATFORM_GROUPS.values()
        for console in consoles
    })

    has_filters = any([
        search,
        platform_filter,
        status_filter,
        achievement_filter,
        ownership_filter,
        min_rating_text,
        max_rating_text,
        sort_by != "recent"
    ])

    return render_template(
        "index.html",
        games=games,
        profile_message=profile_message,
        search=search,
        platform_filter=platform_filter,
        status_filter=status_filter,
        achievement_filter=achievement_filter,
        ownership_filter=ownership_filter,
        min_rating=min_rating_text,
        max_rating=max_rating_text,
        sort_by=sort_by,
        platform_options=platform_options,
        has_filters=has_filters
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_game():

    if request.method == "POST":
        title = request.form["title"].strip()
        platform = request.form["platform"].strip()
        rating = request.form["rating"]
        review = request.form["review"]

        achievements_complete = request.form.get(
            "achievements_complete",
            "No"
        )

        hours_raw = request.form.get("hours_played", "").strip()

        if achievements_complete not in {"Yes", "No"}:
            return render_template(
                "add_game.html",
                platform_groups=PLATFORM_GROUPS,
                error="Invalid achievements option."
            )

        try:
            rating_value = float(rating)

            if (
                rating_value < 0.1
                or rating_value > 10
                or round(rating_value, 1) != rating_value
            ):
                raise ValueError

        except ValueError:
            return render_template(
                "add_game.html",
                platform_groups=PLATFORM_GROUPS,
                error="Rating must be between 0.1 and 10.0, using up to one decimal place."
            )

        if hours_raw:
            try:
                hours_played = float(hours_raw)

                if hours_played < 0:
                    raise ValueError

            except ValueError:
                return render_template(
                    "add_game.html",
                    platform_groups=PLATFORM_GROUPS,
                    error="Hours played must be a positive number."
                )
        else:
            hours_played = None

        connection = get_connection()

        connection.execute("""
            INSERT INTO games (
                title,
                platform,
                rating,
                review,
                achievements_complete,
                hours_played,
                user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            platform,
            rating_value,
            review,
            achievements_complete,
            hours_played,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        return redirect("/")

    return render_template(
        "add_game.html",
        platform_groups=PLATFORM_GROUPS,
        selected_platform=""
    )

@app.route("/game/<int:game_id>")
@login_required
def game(game_id):

    connection = get_connection()

    game = connection.execute("""
        SELECT *
        FROM games
        WHERE id = ?
        AND user_id = ?
    """, (
        game_id,
        session["user_id"]
    )).fetchone()

    connection.close()

    if game is None:
        return "Game not found", 404

    return render_template(
        "game.html",
        game=game
    )


@app.route("/game/<int:game_id>/edit", methods=["GET", "POST"])
@login_required
def edit_game(game_id):

    connection = get_connection()

    game = connection.execute("""
        SELECT *
        FROM games
        WHERE id = ?
        AND user_id = ?
    """, (
        game_id,
        session["user_id"]
    )).fetchone()

    if game is None:
        connection.close()
        return "Game not found", 404

    # Work out which platforms the game currently has.
    selected_platforms = [
        platform.strip()
        for platform in (game["platform"] or "").split(",")
        if platform.strip()
    ]

    if request.method == "POST":

        title = request.form["title"].strip()

        # Get all selected platforms from the form.
        platforms = [
            platform.strip()
            for platform in request.form.getlist("platform")
            if platform.strip()
        ]

        # Remove duplicates while keeping the original order.
        platforms = list(dict.fromkeys(platforms))

        if len(platforms) > 2:
            connection.close()

            return render_template(
                "edit_game.html",
                game=game,
                platform_groups=PLATFORM_GROUPS,
                selected_platforms=platforms,
                error="You can choose a maximum of 2 platforms."
            )

        platform = ", ".join(platforms)

        rating = request.form["rating"].strip()
        review = request.form["review"]

        achievements_complete = request.form.get(
            "achievements_complete",
            ""
        ).strip()

        hours_raw = request.form.get(
            "hours_played",
            ""
        ).strip()

        status = request.form.get(
            "status",
            ""
        ).strip()

        times_played_raw = request.form.get(
            "times_played",
            ""
        ).strip()

        ownership_type = request.form.get(
            "ownership_type",
            ""
        ).strip()

        # Check rating.
        try:
            rating_value = float(rating)

            if (
                rating_value < 0.1
                or rating_value > 10
                or round(rating_value, 1) != rating_value
            ):
                raise ValueError

        except ValueError:
            connection.close()

            return render_template(
                "edit_game.html",
                game=game,
                platform_groups=PLATFORM_GROUPS,
                selected_platforms=platforms,
                error="Rating must be between 0.1 and 10.0, using up to one decimal place."
            )

        # Check Platinum / All achievements.
        if achievements_complete not in {"", "Yes", "No"}:
            connection.close()

            return render_template(
                "edit_game.html",
                game=game,
                platform_groups=PLATFORM_GROUPS,
                selected_platforms=platforms,
                error="Please select a valid achievement option."
            )

        # Check hours played.
        if hours_raw:
            try:
                hours_played = float(hours_raw)

                if hours_played < 0:
                    raise ValueError

            except ValueError:
                connection.close()

                return render_template(
                    "edit_game.html",
                    game=game,
                    platform_groups=PLATFORM_GROUPS,
                    selected_platforms=platforms,
                    error="Hours Played must be 0 or more."
                )
        else:
            hours_played = None

        # Check status.
        if status not in {"", "Completed", "Playing", "Did not finish"}:
            connection.close()

            return render_template(
                "edit_game.html",
                game=game,
                platform_groups=PLATFORM_GROUPS,
                selected_platforms=platforms,
                error="Please select a valid status."
            )

        # Check Times Played.
        if times_played_raw:
            try:
                times_played = int(times_played_raw)

                if times_played < 0:
                    raise ValueError

            except ValueError:
                connection.close()

                return render_template(
                    "edit_game.html",
                    game=game,
                    platform_groups=PLATFORM_GROUPS,
                    selected_platforms=platforms,
                    error="Times Played must be a whole number of 0 or more."
                )
        else:
            times_played = None

        # Check Physical / Digital.
        if ownership_type not in {"", "Physical", "Digital"}:
            connection.close()

            return render_template(
                "edit_game.html",
                game=game,
                platform_groups=PLATFORM_GROUPS,
                selected_platforms=platforms,
                error="Please select Physical or Digital."
            )

        # Save everything.
        connection.execute("""
            UPDATE games
            SET title = ?,
                platform = ?,
                rating = ?,
                review = ?,
                achievements_complete = ?,
                hours_played = ?,
                status = ?,
                times_played = ?,
                ownership_type = ?
            WHERE id = ?
            AND user_id = ?
        """, (
            title,
            platform,
            rating_value,
            review,
            achievements_complete,
            hours_played,
            status,
            times_played,
            ownership_type,
            game_id,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("game", game_id=game_id))

    connection.close()

    return render_template(
        "edit_game.html",
        game=game,
        platform_groups=PLATFORM_GROUPS,
        selected_platforms=selected_platforms
    )


@app.route("/game/<int:game_id>/delete", methods=["POST"])
@login_required
def delete_game(game_id):

    connection = get_connection()

    connection.execute("""
        DELETE FROM games
        WHERE id = ?
        AND user_id = ?
    """, (
        game_id,
        session["user_id"]
    ))

    connection.commit()
    connection.close()

    return redirect("/")

@app.context_processor
def inject_footer():
    connection = get_connection()

    footer = connection.execute("""
        SELECT footer_content
        FROM site_settings
        WHERE id = 1
    """).fetchone()

    connection.close()

    return {
        "footer_content": footer["footer_content"] if footer else ""
    }

@app.route("/version-history")
def version_history():
    connection = get_connection()

    version_history = connection.execute("""
        SELECT *
        FROM version_history
        WHERE id = 1
    """).fetchone()

    connection.close()

    is_admin = session.get("username") == app.config.get("ADMIN_USERNAME")

    return render_template(
        "version_history.html",
        version_history=version_history,
        is_admin=is_admin
    )

@app.route("/version-history/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_version_history():

    connection = get_connection()

    version_history = connection.execute("""
        SELECT *
        FROM version_history
        WHERE id = 1
    """).fetchone()

    if request.method == "POST":
        content = request.form["content"]

        connection.execute("""
            UPDATE version_history
            SET content = ?
            WHERE id = 1
        """, (content,))

        connection.commit()
        connection.close()

        return redirect(url_for("version_history"))

    connection.close()

    return render_template(
        "edit_version_history.html",
        version_history=version_history
    )



@app.route("/footer/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_footer():

    connection = get_connection()

    footer = connection.execute("""
        SELECT *
        FROM site_settings
        WHERE id = 1
    """).fetchone()

    if request.method == "POST":
        content = request.form["content"]

        connection.execute("""
            UPDATE site_settings
            SET footer_content = ?
            WHERE id = 1
        """, (content,))

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    connection.close()

    return render_template(
        "edit_footer.html",
        footer=footer
    )

@app.route("/profile-message", methods=["POST"])
@login_required
def update_profile_message():
    message = request.form["profile_message"].strip()

    if not message:
        message = "My games. My ratings. My reviews."

    connection = get_connection()

    connection.execute("""
        UPDATE users
        SET profile_message = ?
        WHERE username = ?
    """, (message, session["username"]))

    connection.commit()
    connection.close()

    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )