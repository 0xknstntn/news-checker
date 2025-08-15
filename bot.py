import requests
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os

from dotenv import load_dotenv

load_dotenv()

async def send_message_to_api(payload: dict):
        url = f"http://news-checker-api:5555/{os.getenv('API_KEY')}"
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                        print(f"API error {response.status_code}: {response.text}")
                

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
                "**👋 Welcome to Fact-Check Bot!**\n"
                "Send me any news article, statement, or URL, and I’ll quickly research reliable sources to:\n"
                "- ✅ Check if it’s true or false\n"
                "- 📊 Give a credibility score in %\n"
                "- 🔍 Show evidence from multiple sources\n"
                "- ⚠ Highlight contradictions or missing info\n\n"
                "**How to use:**\n"
                "1. Paste a news text or link here 📎\n"
                "2. Wait a few seconds for analysis ⏳\n"
                "3. Get a structured verdict with sources 📚\n\n"
                "_Note: I always answer in the same language as your message._"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text
        chat_id = update.message.chat.id

        payload = {
                "message": user_message,
                "chat_id": chat_id
        }
        await send_message_to_api(payload)
        print(f"Send payload: {payload}")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f"Error: {context.error}")

def main():
        app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN_CHAT")).build()

        app.add_handler(CommandHandler("start", start))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        app.add_error_handler(error)

        print("Bot started...")
        app.run_polling()

if __name__ == "__main__":
        main()