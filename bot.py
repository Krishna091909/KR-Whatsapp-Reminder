import os
import pandas as pd
import asyncio
import threading
import requests
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")
VERITAS_LINK = os.getenv("VERITAS_LINK")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# Flask app to keep alive on Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# Message Template
def create_sms(name, loan_no, advance, edi, overdue, payable):
    return (
        f"\U0001F44B ప్రియమైన {name} గారు,\n\n"
        f"మీ Veritas Finance లో ఉన్న {loan_no} లోన్ నంబరుకు పెండింగ్ అమౌంట్ వివరాలు:\n\n"
        f"\U0001F4B8 అడ్వాన్స్ మొత్తం: ₹{advance}\n"
        f"\U0001F4CC ఈడీ మొత్తం: ₹{edi}\n"
        f"\U0001F534 ఓవర్‌డ్యూ మొత్తం: ₹{overdue}\n"
        f"\u2705 చెల్లించవలసిన మొత్తం: ₹{payable}\n\n"
        f"\u26A0️ దయచేసి వెంటనే చెల్లించండి, లేకపోతే పెనాల్టీలు మరియు CIBIL స్కోర్‌పై ప్రభావం పడుతుంది.\n"
        f"\U0001F517 చెల్లించడానికి లింక్: {VERITAS_LINK}"
    )

# Send SMS

def send_sms(mobile, message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "route": "q",
        "message": message,
        "language": "unicode",
        "numbers": str(mobile)
    }
    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(url, data=payload, headers=headers)
    return response.status_code == 200

# Start command
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Upload File")], [KeyboardButton("About Bot")]], resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"Hey {user.first_name} \\u270C\nThis bot is developed by @ItsKing000.\n\nIt will send Bulk SMS for the users from Excel data.",
        reply_markup=get_main_keyboard()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "About Bot":
        await update.message.reply_text(
            "This bot helps send payment reminder SMS to customers using Excel data.",
            reply_markup=get_main_keyboard()
        )
    elif text == "Upload File":
        await update.message.reply_text("Please send the Excel file (xlsx format only).", reply_markup=get_main_keyboard())

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    file = await update.message.document.get_file()
    file_path = f"/tmp/{file.file_id}.xlsx"
    await file.download_to_drive(file_path)
    threading.Thread(target=process_excel, args=(file_path, context)).start()
    await update.message.reply_text("Processing and sending SMS... Please wait.")

# Processing Excel file
def process_excel(file_path, context):
    df = pd.read_excel(file_path, header=2)
    df = df[df['COLLECTION USER'].str.upper() == 'KONA GOPALA KRISHNA']

    sent_users = []
    skipped_users = []

    for index, row in df.iterrows():
        try:
            name = row['CUSTOMER NAME']
            loan_no = row['LOAN A/C NO']
            mobile = str(int(row['MOBILE NO']))
            edi = float(row['EDI AMOUNT'])
            overdue = float(row['OVER DUE'])
            advance = float(row['ADVANCE'])
            payable = round((edi + overdue) - advance)

            if payable <= 0:
                skipped_users.append(name)
                continue

            msg = create_sms(name, loan_no, advance, edi, overdue, payable)
            success = send_sms(mobile, msg)
            if success:
                sent_users.append(name)
            else:
                skipped_users.append(name)
        except Exception as e:
            skipped_users.append(row.get('CUSTOMER NAME', 'Unknown'))

    report = f"\n\U0001F4E4 *SMS Report*\n\n✅ Sent: {len(sent_users)}\n⛔ Skipped: {len(skipped_users)}\n\n👥 Sent to:\n" + \
             "\n".join(sent_users) + "\n\n🙅 Skipped:\n" + "\n".join(skipped_users)

    asyncio.run(send_report(context, report))

async def send_report(context, report):
    await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=report, parse_mode='Markdown')

# Run Bot
if __name__ == '__main__':
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    application.add_handler(MessageHandler(filters.Document.FILE_EXTENSION("xlsx"), handle_file))

    threading.Thread(target=application.run_polling).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
