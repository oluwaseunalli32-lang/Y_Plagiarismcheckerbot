import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for Render's port binding & webhooks
app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render provides this automatically

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the command /start is issued."""
    welcome_text = (
        "🔍 **Welcome to Y_Plagiarismcheckerbot!**\n\n"
        "Send me any text, and I will scan the web to check for originality and matching sources.\n\n"
        "*Just paste your text below to begin!*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def check_plagiarism(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the incoming text and checks for plagiarism."""
    user_text = update.message.text
    
    if len(user_text.split()) < 3:
        await update.message.reply_text("❌ Please enter a longer text (at least a full sentence) to check.")
        return

    processing_msg = await update.message.reply_text("🕵️‍♂️ *Scanning the web for matches... Please wait.*", parse_mode="Markdown")

    try:
        # Example using a free-tier Plagiarism Checker via RapidAPI 
        # (You can swap this out for Copyleaks, Turnitin API, or a custom search engine)
        url = "https://plagiarism-checker-and-auto-citation.p.rapidapi.com/plagiarism"
        payload = {"text": user_text}
        headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
            "X-RapidAPI-Host": "plagiarism-checker-and-auto-citation.p.rapidapi.com"
        }
        
        response = requests.post(url, json=payload, headers=headers).json()
        
        # Parse results based on typical API responses
        # If using a different API, adjust these dictionary keys accordingly
        plagiarism_percent = response.get("plagiarismPercent", 0)
        unique_percent = 100 - plagiarism_percent
        matches = response.get("matches", [])

        report = f"📊 **Plagiarism Scan Results:**\n"
        report += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        report += f"✨ **Unique Content:** {unique_percent}%\n"
        report += f"🚨 **Plagiarized:** {plagiarism_percent}%\n\n"

        if matches:
            report += "🔗 **Matched Sources:**\n"
            for match in matches[:3]:  # Top 3 sources
                report += f"• [{match.get('title', 'Source')}]({match.get('url')}) ({match.get('matchPercent', '')}% match)\n"
        else:
            report += "✅ No matching sources found online! Your text is unique."

        await processing_msg.edit_text(report, parse_mode="Markdown", disable_web_page_preview=True)

except Exception as e:
        logger.error(f"Error checking plagiarism: {e}")
        await processing_msg.edit_text("❌ An error occurred while scanning your text. Please try again later.")

# --- WEBHOOK & FLASK ROUTING ---

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Receives updates from Telegram and processes them."""
    json_string = request.get_data().decode("utf-8")
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def health_check():
    """Keeps Render happy by responding to its environment pings."""
    return "Bot is running live!", 200

def main():
    global telegram_app
    # Set up the Application
    telegram_app = Application.builder().token(TOKEN).build()

    # Register handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_plagiarism))

    # Initialize the application to prepare the queue
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(telegram_app.initialize())
    loop.run_until_complete(telegram_app.start())

    # Set Telegram webhook point to Render URL
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_url))
    logger.info(f"Webhook set to: {webhook_url}")

if __name__ == "__main__":
    main()
    # Run the Flask app on the port assigned by Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
