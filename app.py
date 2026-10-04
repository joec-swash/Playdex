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

    if session.get("username"):
        user = connection.execute("""
            SELECT id, profile_message
            FROM users
            WHERE username = ?
        """, (session["username"],)).fetchone()

        if user:
            games = connection.execute("""
                SELECT *
                FROM games
                WHERE user_id = ?
                ORDER BY id DESC
            """, (user["id"],)).fetchall()

            profile_message = user["profile_message"]
        else:
            games = []
            profile_message = "My games. My ratings. My reviews."

        user = connection.execute("""
            SELECT profile_message
            FROM users
            WHERE username = ?
        """, (session["username"],)).fetchone()

        profile_message = user["profile_message"]

    else:
        games = []
        profile_message = "My games. My ratings. My reviews."

    connection.close()

    return render_template(
        "index.html",
        games=games,
        profile_message=profile_message
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