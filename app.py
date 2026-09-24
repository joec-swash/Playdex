from flask import Flask, render_template, request, redirect
from database import get_connection, create_table

app = Flask(__name__)


create_table()


@app.route("/")
def home():
    connection = get_connection()

    games = connection.execute("""
        SELECT * FROM games
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template("index.html", games=games)


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


if __name__ == "__main__":
    app.run(debug=True)