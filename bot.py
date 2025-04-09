import os
import asyncio
import pandas as pd
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackQueryHandler
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
VERITAS_LINK = os.getenv("VERITAS_LINK")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Unauthorized user.")
        return

    keyboard = [
        [InlineKeyboardButton("📤 Upload File", callback_data='upload')],
        [InlineKeyboardButton("ℹ️ About Bot", callback_data='about')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Hey {name},\n\n"
        "This bot is developed by @ItsKing000. It will send bulk payment reminder SMS to customers using Excel data.",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'upload':
        await query.edit_message_text("📤 Please upload the Excel file now.")
    elif query.data == 'about':
        await query.edit_message_text(
            "ℹ️ This bot reads Excel files with customer loan details and sends SMS reminders using Fast2SMS API."
        )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Unauthorized user.")
        return

    file = await update.message.document.get_file()
    file_path = "temp.xlsx"
    await file.download_to_drive(file_path)

    df = pd.read_excel(file_path, header=2)
    df = df[df["COLLECTION USER"].str.strip() == "KONA GOPALA KRISHNA"]

    sent_users = []
    skipped_users = []

    for _, row in df.iterrows():
        try:
            name = row["CUSTOMER NAME"]
            loan_no = str(row["LOAN A/C NO"])
            mobile = str(row["MOBILE NO"]).replace(".0", "")
            edi = float(row["EDI AMOUNT"])
            overdue = float(row["OVER DUE"])
            advance = float(row["ADVANCE"])
            payable = (edi + overdue) - advance

            if payable <= 0:
                skipped_users.append(name)
                continue

            msg = (
                f"👋 ప్రియమైన {name} గారు,\n\n"
                f"మీ Veritas Finance లో ఉన్న {loan_no} లోన్ నంబరుకు పెండింగ్ అమౌంట్ వివరాలు:\n\n"
                f"💸 అడ్వాన్స్ మొత్తం: ₹{advance}\n"
                f"📌 ఈడీ మొత్తం: ₹{edi}\n"
                f"🔴 ఓవర్‌డ్యూ మొత్తం: ₹{overdue}\n"
                f"✅ చెల్లించవలసిన మొత్తం: ₹{payable}\n\n"
                f"⚠️ దయచేసి వెంటనే చెల్లించండి, లేకపోతే పెనాల్టీలు మరియు CIBIL స్కోర్‌పై ప్రభావం పడుతుంది.\n"
                f"🔗 చెల్లించడానికి లింక్: {VERITAS_LINK}"
            )

            payload = {
                "authorization": FAST2SMS_API_KEY,
                "message": msg,
                "language": "unicode",
                "route": "q",
                "numbers": mobile
            }

            res = requests.post("https://www.fast2sms.com/dev/bulkV2", data=payload)
            if res.status_code == 200:
                sent_users.append(name)
            else:
                skipped_users.append(name)
        except Exception as e:
            skipped_users.append(row.get("CUSTOMER NAME", "Unknown"))

    sent_text = "\n".join(sent_users) if sent_users else "None"
    skipped_text = "\n".join(skipped_users) if skipped_users else "None"

    report = (
        f"📤 *SMS Report*\n\n"
        f"✅ Sent: {len(sent_users)}\n"
        f"⛔ Skipped: {len(skipped_users)}\n\n"
        f"👥 Sent to:\n{sent_text}\n\n"
        f"🙅 Skipped:\n{skipped_text}"
    )

    await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=report, parse_mode="Markdown")
    await update.message.reply_text("✅ Processing completed. Report sent to log channel.")


if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("xlsx"), handle_file))

    print("Bot running...")
    app.run_polling()
