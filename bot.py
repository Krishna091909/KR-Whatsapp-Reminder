import os
import pandas as pd
import requests
import threading
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
FAST2SMS_API_KEY = "YOUR_FAST2SMS_API_KEY"
ADMIN_CHAT_ID = YOUR_ADMIN_CHAT_ID  # Replace with your Telegram user ID
LOG_CHANNEL_ID = YOUR_LOG_CHANNEL_ID  # Optional: to send summary logs

# --- SMS Sender Function ---
def send_sms(number, message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        "authorization": FAST2SMS_API_KEY
    }
    data = {
        "route": "q",
        "message": message,
        "language": "english",
        "flash": 0,
        "numbers": number
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()

# --- Process Excel File ---
def process_excel(file_path, bot):
    try:
        df = pd.read_excel(file_path, header=2)
    except Exception as e:
        bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Failed to read Excel: {e}")
        return

    sent, skipped = [], []

    for _, row in df.iterrows():
        name = str(row.get("CUSTOMER NAME", "")).strip()
        mobile = str(row.get("MOBILE NO", "")).strip()
        edi = str(row.get("EDI AMOUNT", "")).strip()
        overdue = str(row.get("OVER DUE", "")).strip()
        advance = str(row.get("ADVANCE", "")).strip()
        # collection_user = str(row.get("COLLECTION USER", "")).strip()

        # Optional: Filter by collection user
        # if collection_user != "KONA GOPALA KRISHNA":
        #     skipped.append(name)
        #     continue

        if not mobile or len(mobile) != 10 or not mobile.isdigit():
            skipped.append(name)
            continue

        message = (
            f"📢 మేము మీ రుణ గడువు గురించి తెలియజేస్తున్నాం.\n\n"
            f"👤 పేరు: {name}\n"
            f"📱 మొబైల్: {mobile}\n"
            f"💰 ఇ.డి.ఐ. మొత్తం: ₹{edi}\n"
            f"📅 ఓవర్‌డ్యూ: ₹{overdue}\n"
            f"💵 అడ్వాన్స్: ₹{advance}\n\n"
            f"దయచేసి గడువు లోపు చెల్లించండి.\nధన్యవాదాలు!"
        )

        try:
            res = send_sms(mobile, message)
            if res.get("return") == True:
                sent.append(name)
            else:
                skipped.append(name)
        except Exception:
            skipped.append(name)

    # Report
    report = f"📤 *SMS Report*\n\n✅ Sent: {len(sent)}\n⛔ Skipped: {len(skipped)}\n\n"
    report += f"👥 Sent to:\n" + ("\n".join(sent) if sent else "None") + "\n\n"
    report += f"🙅 Skipped:\n" + ("\n".join(skipped) if skipped else "None")

    bot.send_message(chat_id=ADMIN_CHAT_ID, text=report, parse_mode="Markdown")
    if LOG_CHANNEL_ID:
        bot.send_message(chat_id=LOG_CHANNEL_ID, text=report, parse_mode="Markdown")

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("❌ You are not authorized.")
    await update.message.reply_text("👋 Send the Excel file to start sending SMS reminders.")

async def handle_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return

    document = update.message.document
    if not document.file_name.endswith(".xlsx"):
        return await update.message.reply_text("❌ Please upload a .xlsx Excel file.")

    file = await context.bot.get_file(document.file_id)
    file_path = f"downloads/{document.file_name}"
    os.makedirs("downloads", exist_ok=True)
    await file.download_to_drive(file_path)
    await update.message.reply_text("📄 File received. Processing...")

    threading.Thread(target=process_excel, args=(file_path, context.bot)).start()

# --- Main Bot ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_excel))
    print("✅ Bot is running...")
    app.run_polling()
