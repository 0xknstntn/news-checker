import os
from dotenv import load_dotenv
import requests
import aiohttp

load_dotenv()

async def send_response(text, chat_id):
        try:
                async with aiohttp.ClientSession() as session:
                        async with session.post(
                                f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN_CHAT')}/sendMessage",
                                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
                        ) as response:
                                return await response.json()
        except Exception as e:
                print(f"Error sending response: {e}")
                return {"status": "error", "reason": str(e)}

def send_response_old(message, chat_id):
        url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN_CHAT')}/sendMessage"
        payload = {
                "chat_id": chat_id,
                "text": message
        }
        response = requests.post(url, json=payload)

        if response.status_code == 200:
                return "Message sent successfully"
        else:
                return f"Failed to send message: {response.status_code} - {response.text}"