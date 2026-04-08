import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, threading, time, hashlib, feedparser

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
KANALLAR = ["@bedavainternetorg", "@bedavagirisbio"]
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

# ================= HASH/TEKRAR =================
def hash_al(text):
    return hashlib.md5(text.encode()).hexdigest()

def daha_once(h):
    cursor.execute("SELECT 1 FROM seen WHERE hash=?", (h,))
    return cursor.fetchone()

def kaydet_hash(h):
    cursor.execute("INSERT INTO seen VALUES (?)", (h,))
    conn.commit()

# ================= KANAL KONTROL =================
def check_join(user_id):
    try:
        for kanal in KANALLAR:
            status = bot.get_chat_member(kanal, user_id).status
            if status not in ["member", "administrator", "creator"]:
                return False
        return True
    except:
        return False

# ================= USER =================
def add_user(user_id, ref_by=None):
    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        return

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
    args = msg.text.split()
    ref_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    if not check_join(uid):
        markup = InlineKeyboardMarkup()
        for kanal in KANALLAR:
            link = f"https://t.me/{kanal.replace('@','')}"
            markup.add(InlineKeyboardButton(f"📢 {kanal}", url=link))
        markup.add(InlineKeyboardButton("✅ Katıldım / Kontrol Et", callback_data=f"check_{ref_by if ref_by else 0}"))
        bot.send_message(msg.chat.id, "❗ Botu kullanmak için önce kanallara katıl:", reply_markup=markup)
        return

    add_user(uid, ref_by)
    bot.send_message(msg.chat.id, "🎉 Hoş geldin!\n\n10 referans yap → kampanyalar açılır 🔓", reply_markup=menu())

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    uid = call.from_user.id

    # Katıldım / Kontrol Et butonu
    if call.data.startswith("check_"):
        ref_by = int(call.data.split("_")[1])
        if not check_join(uid):
            bot.answer_callback_query(call.id, "❌ Tüm kanallara katılmamışsın!")
            return
        add_user(uid, ref_by if ref_by != 0 else None)
        bot.edit_message_text("✅ Katılım doğrulandı!\n\n🎉 Artık botu kullanabilirsin.", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Menü açıldı 👇", reply_markup=menu())
        return

    # Diğer butonlar için kanal kontrol
    if not check_join(uid):
        bot.answer_callback_query(call.id, "❗ Önce kanallara katıl!")
        return

    if call.data == "ref":
        refs = get_refs(uid)
        link = f"https://t.me/{bot.get_me().username}?start={uid}"
        bot.send_message(call.message.chat.id, f"👥 {refs}/10 referans\n\n🔗 Linkin:\n{link}")

    elif call.data == "kampanya":
        refs = get_refs(uid)
        if refs < 10:
            bot.send_message(call.message.chat.id, f"❌ 10 referans gerekli ({refs}/10)")
            return
        cursor.execute("SELECT text FROM campaigns ORDER BY id DESC LIMIT 10")
        for c in cursor.fetchall():
            bot.send_message(call.message.chat.id, f"🔥 {c[0]}")

# ================= HERKESE GÖNDER =================
def herkese_gonder(text):
    cursor.execute("SELECT user_id FROM users")
    for u in cursor.fetchall():
        try:
            bot.send_message(u[0], f"🔥 Yeni kampanya:\n\n{text}")
            time.sleep(0.05)
        except:
            pass

# ================= RSS =================
KEYWORDS = ["internet", "gb", "hediye"]
RSS_LIST = ["https://shiftdelete.net/feed", "https://www.webtekno.com/rss.xml"]

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
                    cursor.execute("INSERT INTO campaigns (text) VALUES (?)", (title,))
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
