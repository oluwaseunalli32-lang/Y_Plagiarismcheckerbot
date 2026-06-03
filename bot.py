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
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Initialize Flask
app = Flask(name)

# Initialize Telegram Application globally
telegram_app = Application.builder().token(TOKEN).build()

# Track initialization status
bot_initialized = False

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
    
    if len(user_text) < 40:
        await update.message.reply_text("❌ Text is too short! Please provide a text with a minimum of 40 characters to run a scan.")
        return

    processing_msg = await update.message.reply_text("🕵️‍♂️ *Scanning the web for matches... Please wait.*", parse_mode="Markdown")

    try:
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

        plagiarism_percent = response.get("plagiarismPercent", response.get("plagiarismPercentage", 0))
        unique_percent = 100 - plagiarism_percent
        matches = response.get("sources", response.get("matches", []))

        report = f"📊 **Plagiarism Scan Results:**\n"
        report += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        report += f"✨ **Unique Content:** {unique_percent}%\n"
        report += f"🚨 **Plagiarized:** {plagiarism_percent}%\n\n"

        if matches and plagiarism_percent > 0:
            report += "🔗 **Top Matched Sources:**\n"
            for match in matches[:3]:  
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

# 4. Asynchronous Bot Bootstrapping Function
async def async_initialize_bot():
    """Initializes router loops and ties webhooks down securely."""
    global bot_initialized
    if not bot_initialized:
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_plagiarism))
        
        await telegram_app.initialize()
        await telegram_app.start()
        
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook successfully registered at: {webhook_url}")
        bot_initialized = True

# 5. Webhook & Flask Application Routing
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Listens for incoming updates routed from Telegram."""
    # Ensure bot is ready before taking messages
    if not bot_initialized:
        asyncio.run(async_initialize_bot())
        
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def health_check():
    """Triggers initialization and answers Render pings."""
    if not bot_initialized:
        asyncio.run(async_initialize_bot())
    return "Y_Plagiarismcheckerbot is running live!", 200

# Standalone execution hook
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
