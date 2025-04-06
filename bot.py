import os
import pandas as pd
import datetime
import requests
import time
from flask import Flask
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# 📌 Load from environment or variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ULTRA_INSTANCE_ID = os.getenv("ULTRA_INSTANCE_ID")
ULTRA_TOKEN = os.getenv("ULTRA_TOKEN")
RENDER_URL = os.getenv("RENDER_URL")
VERITAS_LINK = os.getenv("VERITAS_LINK")

# 📁 Save Excel File
SAVE_PATH = "loan_data.xlsx"

# 🔗 UltraMsg API Endpoint
ULTRA_API_URL = f"https://api.ultramsg.com/{ULTRA_INSTANCE_ID}/messages/chat"

# ✅ WhatsApp Sender
def send_whatsapp_message(phone, message):
    payload = {
        "token": ULTRA_TOKEN,
        "to": f"+91{int(phone)}",
        "body": message
    }
    try:
        response = requests.post(ULTRA_API_URL, data=payload)
        print(f" Sent to {phone}: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to send to {phone}: {e}")

# 📊 Process Excel
def process_excel(file_path):
    df = pd.read_excel(file_path)
    for index, row in df.iterrows():
        loan_no = row['LOAN NUMBER']
        name = row['CUSTOMER NAME']
        phone = row['MOBILE NO']
        edi = row['EDI AMOUNT']
        overdue = row['OVER DUE']
        advance = row['ADVANCE']

        payable = edi + overdue - advance

        if payable <= 0:
            continue

        # 📢 Custom Message Format in Telugu with Loan Number and Amount
        msg = (
            f"👋 ప్రియమైన {name} గారు,\n\n"
            f"Veritas Finance నందు మేము మాట్లాడుతున్నాం.\n\n"
"
            f"💳 Veritas Finance నందు మీ లోన్ నెంబర్ {loan_no} కు సంబంధించిన పెండింగ్ అమౌంట్ వివరాలు:\n"
            f"💸 అడ్వాన్స్‌ మొత్తం = ₹{advance}\n"
            f"📌 ఈడీ మొత్తం = ₹{edi}\n"
            f"🔴 ఓవర్‌డ్యూ మొత్తం = ₹{overdue}\n"
            f"✅ మొత్తము చెల్లించవలసిన మొత్తం = ₹{payable}\n\n"
            f"⚠️ దయచేసి వెంటనే చెల్లించండి, లేకపోతే పెనాల్టీలు మరియు CIBIL స్కోర్‌పై ప్రభావం పడుతుంది.\n"
            f"🔗 చెల్లించడానికి లింక్: {VERITAS_LINK}"
        )

        send_whatsapp_message(phone, msg)
        time.sleep(2)  # Add delay between messages

# 📩 Handle Telegram Files
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document and document.file_name.endswith(('.xlsx', '.xls')):
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(SAVE_PATH)
        await update.message.reply_text("📁 File Received, Sending Messages....")

        # �� Process & Send Messages
        process_excel(SAVE_PATH)
        await update.message.reply_text("✅ All Messages Sent.")
    else:
        await update.message.reply_text("⚠️ Please Send Excel File(.xlsx).")

# 🎛 Start Command with Buttons
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📄 Please Send Excel File", callback_data="upload"),
        InlineKeyboardButton("🤖 About The Bot", callback_data="about")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("నేను మీ WhatsApp రిమైండర్ బోట్ ని. దయచేసి క్రింద ఎంపికలతో కొనసగించండి:", reply_markup=reply_markup)

# 🌐 Flask Web Server to Keep Render Alive
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    web_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    while True:
        try:
            response = requests.get(RENDER_URL)
            print(f"Keep-alive ping sent! Status: {response.status_code}")
        except Exception as e:
            print(f"Keep-alive request failed: {e}")
        time.sleep(49)  # Ping every 49 seconds

# ▶️ Run Bot
if __name__ == '__main__':
    # 🔀 Run Flask in Background
    threading.Thread(target=run_flask).start()
    threading.Thread(target=keep_alive).start()

    # ▶️ Start Telegram Bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 Telegram WhatsApp Bot Running...")
    app.run_polling()
