import os
import logging
import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request

# 1. Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Environment Variables & App Instantiation
TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render populates this automatically
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Initialize Flask
app = Flask(__name__)

# Initialize Telegram Application globally so Gunicorn workers can share it
telegram_app = Application.builder().token(TOKEN).build()

# 3. Telegram Core Logic
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the command /start is issued."""
    welcome_text = (
        "🔍 **Welcome to Y_Plagiarismcheckerbot!**\n\n"
        "Send me any text (minimum 40 characters), and I will scan billions of online pages to check its originality.\n\n"
        "*Just paste your text directly into this chat to begin!*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def check_plagiarism(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text, calls the multilingual RapidAPI endpoint, and returns a breakdown."""
    user_text = update.message.text
    
    # The API specifically requires a minimum of 40 characters
    if len(user_text) < 40:
        await update.message.reply_text("❌ Text is too short! Please provide a text with a minimum of 40 characters to run a scan.")
        return

    processing_msg = await update.message.reply_text("🕵️‍♂️ *Scanning the web for matches... Please wait.*", parse_mode="Markdown")

    try:
        # Configuration explicitly matched to the Multi-Lingual API dashboard
        url = "https://plagiarism-checker-and-auto-citation-generator-multi-lingual.p.rapidapi.com/plagiarism"
        
        payload = {
            "text": user_text,
            "language": "en",
            "includeCitations": False,
            "scrapeSources": False
        }
        
        headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "plagiarism-checker-and-auto-citation-generator-multi-lingual.p.rapidapi.com"
        }
        
        response = requests.post(url, json=payload, headers=headers).json()
        logger.info(f"API Response: {response}")

        # Extract values safely based on API response structures
        # Defaults to 0 if no plagiarism percent key is found
        plagiarism_percent = response.get("plagiarismPercent", response.get("plagiarismPercentage", 0))
        unique_percent = 100 - plagiarism_percent
        matches = response.get("sources", response.get("matches", []))

        report = f"📊 **Plagiarism Scan Results:**\n"
        report += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        report += f"✨ **Unique Content:** {unique_percent}%\n"
        report += f"🚨 **Plagiarized:** {plagiarism_percent}%\n\n"

        if matches and plagiarism_percent > 0:
            report += "🔗 **Top Matched Sources:**\n"
            for match in matches[:3]:  # Display top 3 matching URLs
                match_url = match.get('url', '#')
                match_name = match.get('title', 'Matched Source')
                match_percent = match.get('matchPercent', match.get('percentage', ''))
                
                percent_str = f" ({match_percent}% match)" if match_percent else ""
                report += f"• [{match_name}]({match_url}){percent_str}\n"
        else:
            report += "✅ No matching sources found online! Your content looks perfectly original."

        await processing_msg.edit_text(report, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error executing plagiarism check: {e}")
        await processing_msg.edit_text("❌ An unexpected error occurred while processing your request. Please try again later.")

# 4. Webhook & Flask Application Infrastructure
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Listens for updates routed from Telegram and feeds them into the application queue."""
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def health_check():
    """Simple root endpoint to keep the Render free tier application awake."""
    return "Y_Plagiarismcheckerbot is running live!", 200

# 5. Bootstrapping and Event Loop Handlers
def initialize_bot():
    """Initializes bot routing and configures the remote webhook address via Telegram API."""
    # Register command and text message listeners
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_plagiarism))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(telegram_app.initialize())
    loop.run_until_complete(telegram_app.start())

    # Set up Webhook targeting Render's external URL path
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_url))
    logger.info(f"Webhook successfully registered at: {webhook_url}")

# Execute initialization routines immediately when Gunicorn imports the script
initialize_bot()

# Traditional entrypoint for fallback local executions
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
