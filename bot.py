import os
import pandas as pd
import requests
import time
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

load_dotenv()

# ✅ Environment Variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
VERITAS_LINK = os.getenv("VERITAS_LINK")

# 🔐 Paths & Flags
SAVE_PATH = "data.xlsx"
stop_flag = False


def send_sms(phone, message):
    try:
        payload = {
            'authorization': FAST2SMS_API_KEY,
            'sender_id': 'FSTSMS',
            'message': message,
            'language': 'unicode',
            'route': 'q',
            'numbers': str(phone)
        }
        response = requests.post("https://www.fast2sms.com/dev/bulkV2", data=payload)
        return response.json().get("return", False)
    except Exception as e:
        print(f"❌ SMS Error for {phone}: {e}")
        return False


async def process_excel(bot, chat_id):
    global stop_flag
    stop_flag = False

    df = pd.read_excel(SAVE_PATH, skiprows=2)
    df.columns = df.columns.str.replace('\xa0', ' ').str.strip()
    df = df[df['COLLECTION USER'] == "KONA GOPALA KRISHNA"]

    sent, skipped = 0, 0
    sent_list, skipped_list = [], []

    for index, row in df.iterrows():
        if stop_flag:
            break
        try:
            name = row['CUSTOMER NAME']
            phone = row['MOBILE NO']
            loan = row['LOAN A/C NO']
            edi = row['EDI AMOUNT']
            overdue = row['OVER DUE']
            advance = row['ADVANCE']
            payable = edi + overdue - advance

            if payable <= 0:
                skipped += 1
                skipped_list.append(name)
                continue

            msg = (
                f"👋 ప్రియమైన {name} గారు,\n\n"
                f"మీ Veritas Finance లో ({loan}) లోన్‌కు బకాయి వివరాలు:\n"
                f"💰 అడ్వాన్స్: ₹{advance}\n"
                f"📌 EDI: ₹{edi}\n"
                f"❗ ఓవర్‌డ్యూస్: ₹{overdue}\n"
                f"✅ చెల్లించవలసిన మొత్తం: ₹{payable}\n\n"
                f"📎 చెల్లించండి: {VERITAS_LINK}"
            )

            if send_sms(phone, msg):
                sent += 1
                sent_list.append(name)
            else:
                skipped += 1
                skipped_list.append(name)

            time.sleep(2)

        except Exception as e:
            print(f"⚠️ Error: {e}")
            continue

    report = (
        f"📤 *SMS Report*\n\n"
        f"✅ Sent: {sent}\n⛔ Skipped: {skipped}\n\n"
        f"👥 Sent to:\n" + "\n".join(sent_list[:30]) + "\n\n"
        f"🙅 Skipped:\n" + "\n".join(skipped_list[:30])
    )

    await bot.send_message(chat_id=LOG_CHANNEL_ID, text=report)


# === Telegram Bot Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Access Denied")
        return

    buttons = [
        [InlineKeyboardButton("📤 Upload Excel", callback_data="upload")],
        [InlineKeyboardButton("❌ Stop Sending", callback_data="stop")],
    ]
    await update.message.reply_text("Welcome to Veritas SMS Reminder Bot", reply_markup=InlineKeyboardMarkup(buttons))


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ALLOWED_USER_ID:
        await query.edit_message_text("⛔ Access Denied")
        return

    if query.data == "upload":
        await query.edit_message_text("📎 Please send the Excel file (.xlsx)")
    elif query.data == "stop":
        global stop_flag
        stop_flag = True
        await query.edit_message_text("🛑 Stopping message sending...")


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    doc = update.message.document
    if doc.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("📥 File received. Processing...")
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(SAVE_PATH)
        await update.message.reply_text("📤 Sending SMS...")
        threading.Thread(target=lambda: asyncio.run(process_excel(context.bot, update.effective_chat.id))).start()
    else:
        await update.message.reply_text("⚠️ Please send a valid Excel file")


# === Flask Keep-Alive ===

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is Alive!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# === Run Bot ===

if __name__ == "__main__":
    import asyncio
    threading.Thread(target=run_flask).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

    print("🚀 Bot Started")
    app.run_polling()
