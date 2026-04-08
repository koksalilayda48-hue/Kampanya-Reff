from flask import Flask, request, redirect
import sqlite3

app = Flask(__name__)

def get_db():
    return sqlite3.connect("data.db")

@app.route("/")
def home():
    db = get_db()
    cur = db.cursor()

    users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    campaigns = cur.execute("SELECT * FROM campaigns").fetchall()

    html = f"""
    <h1>Admin Panel</h1>
    <p>👤 Kullanıcı: {users}</p>

    <h2>Kampanya Ekle</h2>
    <form method='post' action='/add'>
        <input name='text' placeholder='Kampanya yaz'>
        <button>Ekle</button>
    </form>

    <h2>Kampanyalar</h2>
    """

    for c in campaigns:
        html += f"<p>🔥 {c[1]} - <a href='/del/{c[0]}'>Sil</a></p>"

    return html

@app.route("/add", methods=["POST"])
def add():
    text = request.form["text"]

    db = get_db()
    db.execute("INSERT INTO campaigns (text) VALUES (?)", (text,))
    db.commit()

    return redirect("/")

@app.route("/del/<id>")
def delete(id):
    db = get_db()
    db.execute("DELETE FROM campaigns WHERE id=?", (id,))
    db.commit()

    return redirect("/")

app.run(host="0.0.0.0", port=10000)
