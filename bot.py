import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, time, threading, hashlib, feedparser, requests

TOKEN = "8205506310:AAGYaEVyxmlGGKNVYc7N7jIbQAA79pJDLnY"
KANAL = "@bedavainternetorg"
ADMIN_ID = 6179118477

bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

# TABLOLAR
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY,
ref_by INTEGER,
refs INTEGER DEFAULT 0,
ip TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS campaigns (
id INTEGER PRIMARY KEY AUTOINCREMENT,
text TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS seen (
hash TEXT PRIMARY KEY
)""")

conn.commit()

# ================= KORUMA =================
def hash_al(text):
    return hashlib.md5(text.encode()).hexdigest()

def daha_once(h):
    cursor.execute("SELECT * FROM seen WHERE hash=?", (h,))
    return cursor.fetchone()

def kaydet_hash(h):
    cursor.execute("INSERT INTO seen VALUES (?)", (h,))
    conn.commit()

# ================= KANAL =================
def check_join(user_id):
    try:
        s = bot.get_chat_member(KANAL, user_id).status
        return s in ["member","administrator","creator"]
    except:
        return False

# ================= USER =================
def add_user(user_id, ref_by=None):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        return

    # kendini referans engelle
    if ref_by == user_id:
        ref_by = None

    cursor.execute("INSERT INTO users VALUES (?,?,0,'')",(user_id,ref_by))
    conn.commit()

    if ref_by:
        cursor.execute("UPDATE users SET refs = refs + 1 WHERE user_id=?", (ref_by,))
        conn.commit()

def get_refs(uid):
    cursor.execute("SELECT refs FROM users WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

# ================= MENÜ =================
def menu():
    m = InlineKeyboardMarkup()
    m.add(
        InlineKeyboardButton("🎁 Kampanyalar", callback_data="kampanya"),
        InlineKeyboardButton("👥 Referans", callback_data="ref")
    )
    return m

# ================= START =================
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id

    if not check_join(uid):
        bot.send_message(msg.chat.id, f"❗ Katıl: {KANAL}")
        return

    args = msg.text.split()
    ref_by = int(args[1]) if len(args)>1 else None

    add_user(uid, ref_by)

    bot.send_message(msg.chat.id,
    "🎉 Hoş geldin\n\n10 referans yap → internet ödülü açılır",
    reply_markup=menu())

# ================= BUTON =================
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    uid = call.from_user.id

    if not check_join(uid):
        bot.answer_callback_query(call.id,"Kanala katıl!")
        return

    if call.data == "ref":
        r = get_refs(uid)
        link = f"https://t.me/{bot.get_me().username}?start={uid}"

        bot.send_message(call.message.chat.id,
        f"👥 {r}/10 referans\n\n🔗 {link}")

    elif call.data == "kampanya":
        r = get_refs(uid)

        if r < 10:
            bot.send_message(call.message.chat.id,
            f"❌ 10 referans gerekli ({r}/10)")
            return

        cursor.execute("SELECT text FROM campaigns")
        for c in cursor.fetchall():
            bot.send_message(call.message.chat.id, f"🔥 {c[0]}")

# ================= GÖNDER =================
def herkese(text):
    cursor.execute("SELECT user_id FROM users")
    for u in cursor.fetchall():
        try:
            bot.send_message(u[0], f"🔥 Yeni:\n{text}")
            time.sleep(0.05)
        except:
            pass

# ================= RSS =================
KEYWORDS = ["internet","gb","hediye"]

RSS_LIST = [
"https://shiftdelete.net/feed",
"https://www.webtekno.com/rss.xml"
]

def rss():
    while True:
        for url in RSS_LIST:
            feed = feedparser.parse(url)

            for e in feed.entries[:10]:
                t = e.title.lower()

                if not any(k in t for k in KEYWORDS):
                    continue

                h = hash_al(t)

                if daha_once(h):
                    continue

                kaydet_hash(h)

                cursor.execute("INSERT INTO campaigns(text) VALUES(?)",(e.title,))
                conn.commit()

                herkese(e.title)

        time.sleep(600)

# ================= THREAD =================
threading.Thread(target=rss).start()

bot.infinity_polling()
