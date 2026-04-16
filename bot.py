import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, threading, time
from flask import Flask

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
KANALLAR = ["@bedavainternetorg", "@bedavagirisbio", "@vipgrubum"]
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
        return  # fake ref engel

    if ref_by == user_id:
        ref_by = None

    cursor.execute(
        "INSERT INTO users (user_id, ref_by, refs) VALUES (?, ?, 0)",
        (user_id, ref_by)
    )
    conn.commit()

    if ref_by:
        cursor.execute("SELECT 1 FROM users WHERE user_id=?", (ref_by,))
        if cursor.fetchone():
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
        InlineKeyboardButton("👥 Referansım", callback_data="ref"),
        InlineKeyboardButton("🎁 Ödüller", callback_data="odul")
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

        markup.add(InlineKeyboardButton("✅ Katıldım / Devam Et", callback_data=f"check_{ref_by if ref_by else 0}"))

        bot.send_message(msg.chat.id,
        "🚨 Devam etmek için kanallara katıl:",
        reply_markup=markup)
        return

    add_user(uid, ref_by)
    bot.send_message(msg.chat.id, "🎉 Hoş geldin!", reply_markup=menu())

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    uid = call.from_user.id

    if call.data.startswith("check_"):
        ref_by = int(call.data.split("_")[1])

        if not check_join(uid):
            bot.answer_callback_query(call.id, "❌ Katılmadan devam edemezsin!")
            return

        add_user(uid, ref_by if ref_by != 0 else None)

        bot.edit_message_text(
            "✅ Katılım doğrulandı!\n\n🎉 Hoş geldin.",
            call.message.chat.id,
            call.message.message_id
        )

        bot.send_message(call.message.chat.id, "Menü:", reply_markup=menu())
        return

    if not check_join(uid):
        bot.answer_callback_query(call.id, "❗ Önce kanallara katıl!")
        return

    # REFERANS
    if call.data == "ref":
        refs = get_refs(uid)
        link = f"https://t.me/{bot.get_me().username}?start={uid}"

        bot.send_message(call.message.chat.id,
f"""👥 Referansın: {refs}

🔗 Davet linkin:
{link}

🎯 Ödüller:
• 5 kişi → Vodafone 1-3GB
• 5 kişi → Turkcell 1GB

📩 İletişim: @Weghrumi2""")

    # ÖDÜL
    elif call.data == "odul":
        refs = get_refs(uid)

        if refs >= 5:
            text = "🎉 5 referans tamamlandı!\n➡️ Turkcell 1GB kazandın\n📩 @Weghrumi2"
        elif refs >= 5:
            text = "🎉 5 referans tamamlandı!\n➡️ Vodafone 1-3GB kazandın\n📩 @Weghrumi2"
        else:
            text = "❌ Henüz ödül yok.\n\n3 kişi → Vodafone\n5 kişi → Turkcell"

        bot.send_message(call.message.chat.id, text)

# ================= FLASK (PORT) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot aktif!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= BAŞLAT =================
print("Bot çalışıyor...")

threading.Thread(target=run_web).start()

bot.infinity_polling()
