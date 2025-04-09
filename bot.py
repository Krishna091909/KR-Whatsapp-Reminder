import os
import pandas as pd
import datetime
import requests
import time
from flask import Flask
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")
RENDER_URL = os.getenv("RENDER_URL")
VERITAS_LINK = os.getenv("VERITAS_LINK")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# 📁 File Paths
SAVE_PATH = "loan_data.xlsx"
stop_sending = False


def send_sms(phone, message):
    payload = {
        'authorization': FAST2SMS_API_KEY,
        'sender_id': 'FSTSMS',
        'message': message,
        'language': 'unicode',
        'route': 'q',
        'numbers': str(phone)
    }
    try:
        response = requests.post("https://www.fast2sms.com/dev/bulkV2", data=payload)
        result = response.json()
        return result.get("return", False)
    except Exception as e:
        print(f"❌ Error sending SMS to {phone}: {e}")
        return False


# 📊 Process Excel
def process_excel(file_path, application):
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
                f"\U0001F44B ప్రియమైన {name} గారు,\n\n"
                f"మీ Veritas Finance లో ఉన్న {loan_no} లోన్ నంబరుకు పెండింగ్ అమౌంట్ వివరాలు:\n\n"
                f"\U0001F4B8 అడ్వాన్స్ Amount: ₹{advance}\n"
                f"\U0001F4CC Edi Amount: ₹{edi}\n"
                f"\U0001F534 Overdue Amount: ₹{overdue}\n"
                f"\u2705 చెల్లించవలసిన మొత్తం: ₹{payable}\n\n"
                f"\u26A0\uFE0F దయచేసి వెంటనే చెల్లించండి, లేకపోతే పెనాల్టీలు మరియు CIBIL స్కోర్‌పై ప్రభావం పడుతుంది.\n"
                f"\U0001F517 చెల్లించడానికి లింక్: {VERITAS_LINK}"
            )

            if send_sms(phone, msg):
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
        f"🧾 SMS Reminder Report:\n"
        f"✅ Sent: {sent_count}\n"
        f"⛔ Skipped: {skip_count}\n\n"
        f"👥 Sent To:\n" + "\n".join(sent_users[:30]) + "\n\n"
        f"🙅‍♂️ Skipped:\n" + "\n".join(skipped_users[:30])
    )

    async def send_log():
        await application.bot.send_message(chat_id=LOG_CHANNEL_ID, text=report)

    application.create_task(send_log())


# 📩 Handle File Upload
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("🚫 Access Denied.")
        return

    document = update.message.document
    if document.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("📥 File received. Processing...")
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(SAVE_PATH)
        await update.message.reply_text("📤 Sending SMS reminders...")
        threading.Thread(target=process_excel, args=(SAVE_PATH, context.application)).start()
    else:
        await update.message.reply_text("⚠️ Please send an Excel (.xlsx) file.")


# 🤖 Bot Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("🚫 Access Denied.")
        return

    keyboard = [[
        InlineKeyboardButton("📄 Upload Excel", callback_data="upload"),
        InlineKeyboardButton("ℹ️ About", callback_data="about")
    ]]
    await update.message.reply_text("Welcome to SMS Reminder Bot!", reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "upload":
        await query.edit_message_text("📁 Send your Excel file (.xlsx)")
    elif query.data == "about":
        await query.edit_message_text("🤖 Developed for Veritas SMS Reminders based on Excel data.")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_sending
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    stop_sending = True
    await update.message.reply_text("🛑 Sending stopped.")


# 🌐 Flask Keep-Alive
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
