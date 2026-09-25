from functools import wraps
import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for
)

from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection, create_table

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    app.config.from_pyfile("config.py")

create_table()


def login_required(route):
    @wraps(route)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

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

    connection.close()

    return render_template(
        "index.html",
        games=games,
        search=search
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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )