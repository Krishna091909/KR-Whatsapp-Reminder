import os
import pandas as pd
import datetime
import requests
import time
from flask import Flask
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# 🔐 Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ULTRA_INSTANCE_ID = os.getenv("ULTRA_INSTANCE_ID")
ULTRA_TOKEN = os.getenv("ULTRA_TOKEN")
RENDER_URL = os.getenv("RENDER_URL")
VERITAS_LINK = os.getenv("VERITAS_LINK")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# 📁 Paths
SAVE_PATH = "loan_data.xlsx"
IMAGE_PATH = "reminder.jpg"  # Add this image in your repo

ULTRA_API_URL = f"https://api.ultramsg.com/{ULTRA_INSTANCE_ID}/contacts/check"
ULTRA_MSG_URL = f"https://api.ultramsg.com/{ULTRA_INSTANCE_ID}/messages/image"

stop_sending = False

# ✅ WhatsApp Sender
def is_whatsapp_user(phone):
    payload = {
        "token": ULTRA_TOKEN,
        "contacts": f"+91{int(phone)}"
    }
    try:
        response = requests.post(ULTRA_API_URL, data=payload)
        data = response.json()
        return data[0]["status"] == "valid"
    except:
        return False

def send_whatsapp_image(phone, message):
    payload = {
        "token": ULTRA_TOKEN,
        "to": f"+91{int(phone)}",
        "image": f"{VERITAS_LINK}/reminder.jpg",
        "caption": message
    }
    try:
        requests.post(ULTRA_MSG_URL, data=payload)
    except Exception as e:
        print(f"❌ Error sending to {phone}: {e}")

# 📊 Process Excel
def process_excel(file_path, bot):
    global stop_sending
    stop_sending = False

    df = pd.read_excel(file_path, skiprows=2)
    df.columns = df.columns.str.replace('\xa0', ' ').str.strip()
    df = df[df['COLLECTION USER'] == "KONA GOPALA KRISHNA"]

    sent_count, skip_count = 0, 0
    sent_users, skipped_users = [], []

    for index, row in df.iterrows():
        if stop_sending:
            break
        try:
            phone = row['MOBILE NO']
            name = row['CUSTOMER NAME']
            loan_no = row['LOAN A/C NO']
            edi = row['EDI AMOUNT']
            overdue = row['OVER DUE']
            advance = row['ADVANCE']
            payable = edi + overdue - advance

            if payable <= 0:
                continue

            msg = (
                f"👋 ప్రియమైన {name} గారు,\n\n"
                f"మీ Veritas Finance లో ఉన్న {loan_no} లోన్ నంబరుకు పెండింగ్ అమౌంట్ వివరాలు:\n\n"
                f"💸 అడ్వాన్స్ Amount: ₹{advance}\n"
                f"📌 Edi Amount: ₹{edi}\n"
                f"🔴 Overdue Amount: ₹{overdue}\n"
                f"✅ చెల్లించవలసిన మొత్తం: ₹{payable}\n\n"
                f"⚠️ దయచేసి వెంటనే చెల్లించండి, లేకపోతే పెనాల్టీలు మరియు CIBIL స్కోర్‌పై ప్రభావం పడుతుంది.\n"
                f"🔗 చెల్లించడానికి లింక్: {VERITAS_LINK}"
            )

            if is_whatsapp_user(phone):
                send_whatsapp_image(phone, msg)
                sent_count += 1
                sent_users.append(name)
            else:
                skip_count += 1
                skipped_users.append(name)

            time.sleep(2)
        except Exception as e:
            print(f"❌ Error processing row {index}: {e}")

    # 🔔 Send log to Telegram
    report = (
        f"🧾 WhatsApp Reminder Report:\n"
        f"✅ Sent: {sent_count}\n"
        f"⛔ Skipped: {skip_count}\n\n"
        f"👥 Sent To:\n" + "\n".join(sent_users[:30]) + "\n\n"
        f"🙅‍♂️ Skipped:\n" + "\n".join(skipped_users[:30])
    )

    bot.send_message(chat_id=LOG_CHANNEL_ID, text=report)

# 📩 Handle Files
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("🚫 Access Denied.")
        return

    document = update.message.document
    if document.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("📥 File received. Processing...")
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(SAVE_PATH)
        await update.message.reply_text("📤 Sending WhatsApp messages...")
        threading.Thread(target=process_excel, args=(SAVE_PATH, context.bot)).start()
    else:
        await update.message.reply_text("⚠️ Please send an Excel (.xlsx) file.")

# 🤖 Bot Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("🚫 Access Denied.")
        return

    keyboard = [[
        InlineKeyboardButton("📄 Upload Excel", callback_data="upload"),
        InlineKeyboardButton("ℹ️ About", callback_data="about")
    ]]
    await update.message.reply_text("Welcome to WhatsApp Reminder Bot!", reply_markup=InlineKeyboardMarkup(keyboard))

# 🔘 Button Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "upload":
        await query.edit_message_text("📁 Send your Excel file (.xlsx)")
    elif query.data == "about":
        await query.edit_message_text("🤖 Developed by @ItsKing000. Sends reminders via WhatsApp based on Excel data.")

# 🛑 Stop Command
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_sending
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    stop_sending = True
    await update.message.reply_text("🛑 Sending stopped.")

# 🌐 Flask to keep alive
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is Alive!"

def run_flask():
    web_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL)
        except:
            pass
        time.sleep(49)

# ▶️ Run Bot
if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    threading.Thread(target=keep_alive).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🚀 Bot running...")
    app.run_polling()
