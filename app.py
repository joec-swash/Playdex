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
@login_required
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
@login_required
def home():

    search = request.args.get("search", "").strip()

    connection = get_connection()

    if search:

        games = connection.execute("""
            SELECT *
            FROM games
            WHERE user_id = ?
            AND title LIKE ?
            ORDER BY id DESC
        """, (
            session["user_id"],
            f"%{search}%"
        )).fetchall()

    else:

        games = connection.execute("""
            SELECT *
            FROM games
            WHERE user_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

    user = connection.execute("""
        SELECT profile_message
        FROM users
        WHERE username = ?
    """, (session["username"],)).fetchone()

    connection.close()

    return render_template(
        "index.html",
        games=games,
        profile_message=user["profile_message"]
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_game():

    if request.method == "POST":

        title = request.form["title"]
        platform = request.form["platform"]
        rating = request.form["rating"]
        review = request.form["review"]

        connection = get_connection()

        connection.execute("""
            INSERT INTO games (
                title,
                platform,
                rating,
                review,
                user_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            title,
            platform,
            rating,
            review,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        return redirect("/")

    return render_template("add_game.html")


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

    return render_template("game.html", game=game)


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

    if request.method == "POST":

        title = request.form["title"]
        platform = request.form["platform"]
        rating = request.form["rating"]
        review = request.form["review"]

        connection.execute("""
            UPDATE games
            SET title = ?,
                platform = ?,
                rating = ?,
                review = ?
            WHERE id = ?
            AND user_id = ?
        """, (
            title,
            platform,
            rating,
            review,
            game_id,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        return redirect(f"/game/{game_id}")

    connection.close()

    return render_template(
        "edit_game.html",
        game=game
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