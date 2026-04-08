import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, time, threading, hashlib, feedparser

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
KANAL = os.getenv("CHANNEL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise Exception("BOT_TOKEN yok!")

bot = telebot.TeleBot(TOKEN)

# ================= DB =================
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    ref_by INTEGER,
    refs INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS seen (
    hash TEXT PRIMARY KEY
)
""")

conn.commit()

# ================= KORUMA =================
def hash_al(text):
    return hashlib.md5(text.encode()).hexdigest()

def daha_once(h):
    cursor.execute("SELECT 1 FROM seen WHERE hash=?", (h,))
    return cursor.fetchone()

def kaydet_hash(h):
    cursor.execute("INSERT INTO seen VALUES (?)", (h,))
    conn.commit()

# ================= KANAL =================
def check_join(user_id):
    try:
        status = bot.get_chat_member(KANAL, user_id).status
        return status in ["member", "administrator", "creator"]
    except:
        return False

# ================= USER =================
def add_user(user_id, ref_by=None):
    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        return

    # kendini referans engelle
    if ref_by == user_id:
        ref_by = None

    cursor.execute(
        "INSERT INTO users (user_id, ref_by, refs) VALUES (?, ?, 0)",
        (user_id, ref_by)
    )
    conn.commit()

    if ref_by:
        cursor.execute("UPDATE users SET refs = refs + 1 WHERE user_id=?", (ref_by,))
        conn.commit()

def get_refs(user_id):
    cursor.execute("SELECT refs FROM users WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    return r[0] if r else 0

# ================= MENÜ =================
def menu():
    m = InlineKeyboardMarkup()
    m.add(
        InlineKeyboardButton("🎁 Kampanyalar", callback_data="kampanya"),
        InlineKeyboardButton("👥 Referansım", callback_data="ref")
    )
    return m

# ================= START =================
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id

    if not check_join(uid):
        bot.send_message(msg.chat.id, f"❗ Önce kanala katıl:\n{KANAL}")
        return

    args = msg.text.split()
    ref_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    add_user(uid, ref_by)

    bot.send_message(
        msg.chat.id,
        "🎉 Hoş geldin!\n\n"
        "📶 10 referans yap → kampanyaları aç 🔓",
        reply_markup=menu()
    )

# ================= BUTON =================
@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    uid = call.from_user.id

    if not check_join(uid):
        bot.answer_callback_query(call.id, "Kanala katılman gerekiyor!")
        return

    if call.data == "ref":
        refs = get_refs(uid)
        link = f"https://t.me/{bot.get_me().username}?start={uid}"

        bot.send_message(
            call.message.chat.id,
            f"👥 Referans: {refs}/10\n\n🔗 Linkin:\n{link}"
        )

    elif call.data == "kampanya":
        refs = get_refs(uid)

        if refs < 10:
            bot.send_message(
                call.message.chat.id,
                f"❌ 10 referans gerekli!\n\nŞu an: {refs}/10"
            )
            return

        cursor.execute("SELECT text FROM campaigns ORDER BY id DESC LIMIT 10")
        data = cursor.fetchall()

        if not data:
            bot.send_message(call.message.chat.id, "❗ Şu an kampanya yok.")
        else:
            for c in data:
                bot.send_message(call.message.chat.id, f"🔥 {c[0]}")

# ================= HERKESE GÖNDER =================
def herkese_gonder(text):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    for u in users:
        try:
            bot.send_message(u[0], f"🔥 Yeni kampanya:\n\n{text}")
            time.sleep(0.05)
        except:
            pass

# ================= RSS =================
KEYWORDS = ["internet", "gb", "hediye"]

RSS_LIST = [
    "https://shiftdelete.net/feed",
    "https://www.webtekno.com/rss.xml"
]

def rss_worker():
    while True:
        try:
            for url in RSS_LIST:
                feed = feedparser.parse(url)

                for entry in feed.entries[:10]:
                    title = entry.title.strip()
                    low = title.lower()

                    if not any(k in low for k in KEYWORDS):
                        continue

                    h = hash_al(low)

                    if daha_once(h):
                        continue

                    kaydet_hash(h)

                    cursor.execute(
                        "INSERT INTO campaigns (text) VALUES (?)",
                        (title,)
                    )
                    conn.commit()

                    print("Yeni kampanya:", title)

                    herkese_gonder(title)

        except Exception as e:
            print("RSS Hata:", e)

        time.sleep(600)

# ================= THREAD =================
threading.Thread(target=rss_worker, daemon=True).start()

print("Bot çalışıyor...")
bot.infinity_polling(skip_pending=True)
