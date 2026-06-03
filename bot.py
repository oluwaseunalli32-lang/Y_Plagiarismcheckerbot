import os
import logging
import requests
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Environment Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def escape_markdown_v2(text: str) -> str:
    """Escapes reserved Telegram MarkdownV2 characters so messages never break parsing rules."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', str(text))

# 3. Telegram Core Logic
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🔍 *Welcome to Y\_Plagiarismcheckerbot\!*\n\n"
        "Send me any text \(minimum 40 characters\), and I will scan billions of online pages to check its originality\.\n\n"
        "_*Just paste your text directly into this chat to begin\!*_"
    )
    await update.message.reply_text(welcome_text, parse_mode="MarkdownV2")

async def check_plagiarism(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        # Safely build the report using the string escaper to protect the formatting layouts
        report = f"📊 *Plagiarism Scan Results:*\n"
        report += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        report += f"✨ *Unique Content:* {unique_percent}%\n"
        report += f"🚨 *Plagiarized:* {plagiarism_percent}%\n\n"

        if matches and plagiarism_percent > 0:
            report += "🔗 *Top Matched Sources:*\n"
            for match in matches[:3]:  
                match_url = match.get('url', '#')
                # Escape the titles and parameters text so they can't break Markdown rules
                match_name = escape_markdown_v2(match.get('title', 'Matched Source'))
                match_percent = match.get('matchPercent', match.get('percentage', ''))
                
                percent_str = f" \({match_percent}\% match\)" if match_percent else ""
                report += f"• [{match_name}]({match_url}){percent_str}\n"
        else:
            report += "✅ No matching sources found online\! Your content looks perfectly original\."

        await processing_msg.edit_text(report, parse_mode="MarkdownV2", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error executing plagiarism check: {e}")
        await processing_msg.edit_text("❌ An unexpected error occurred while processing your request. Please try again later.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_plagiarism))

    logger.info("Starting bot long-polling loop...")
    application.run_polling()

if __name__ == "__main__":
    main()
