from flask import Flask, render_template, request, redirect
from database import get_connection, create_table

app = Flask(__name__)


create_table()


@app.route("/")
def home():
    search = request.args.get("search", "").strip()

    connection = get_connection()

    if search:
        games = connection.execute("""
            SELECT * FROM games
            WHERE title LIKE ?
            ORDER BY id DESC
        """, (f"%{search}%",)).fetchall()
    else:
        games = connection.execute("""
            SELECT * FROM games
            ORDER BY id DESC
        """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        games=games,
        search=search
    )


@app.route("/add", methods=["GET", "POST"])
def add_game():
    if request.method == "POST":
        title = request.form["title"]
        platform = request.form["platform"]
        rating = request.form["rating"]
        review = request.form["review"]

        connection = get_connection()

        connection.execute("""
            INSERT INTO games (title, platform, rating, review)
            VALUES (?, ?, ?, ?)
        """, (title, platform, rating, review))

        connection.commit()
        connection.close()

        return redirect("/")

    return render_template("add_game.html")


@app.route("/game/<int:game_id>")
def game(game_id):
    connection = get_connection()

    game = connection.execute("""
        SELECT * FROM games
        WHERE id = ?
    """, (game_id,)).fetchone()

    connection.close()

    if game is None:
        return "Game not found", 404

    return render_template("game.html", game=game)


@app.route("/game/<int:game_id>/edit", methods=["GET", "POST"])
def edit_game(game_id):
    connection = get_connection()

    game = connection.execute("""
        SELECT * FROM games
        WHERE id = ?
    """, (game_id,)).fetchone()

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
            SET title = ?, platform = ?, rating = ?, review = ?
            WHERE id = ?
        """, (title, platform, rating, review, game_id))

        connection.commit()
        connection.close()

        return redirect(f"/game/{game_id}")

    connection.close()

    return render_template("edit_game.html", game=game)


@app.route("/game/<int:game_id>/delete", methods=["POST"])
def delete_game(game_id):
    connection = get_connection()

    connection.execute("""
        DELETE FROM games
        WHERE id = ?
    """, (game_id,))

    connection.commit()
    connection.close()

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)