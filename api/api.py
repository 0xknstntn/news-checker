from fastapi import FastAPI, Request, Response, HTTPException
import requests
import json
import os
from pymongo import MongoClient
from datetime import datetime, timedelta
import re
import asyncio
from typing import Dict, List, Optional, Any, Union
import redis
from dotenv import load_dotenv

from .parse_message import parse_message

load_dotenv()

app = FastAPI()

redis_client = None

def get_redis_client():
        global redis_client
        if redis_client is None:
                redis_client = redis.Redis(host=os.getenv("REDIS_HOST"), port=6379, db=0)
        return redis_client

def push_message(message):
        try:
                r = get_redis_client()
                r.lpush(os.getenv("REDIS_QUEUE_KEY"), message)
                print(f"Message pushed: {message}")
        except Exception as e:
                print(f"Error pushing message: {e}")

# Настраиваем выполнение запросов
@app.post(f"/{os.getenv('API_KEY')}")
async def handle_webhook(request: Request):
        try:
                body = await request.json() 
                
                user_message, chat_id = parse_message(body)

                message = {
                        "input": user_message,
                        "chat_id": chat_id,
                        "session_id": f"{chat_id}_session"
                }

                push_message(json.dumps(message, ensure_ascii=False))
        except Exception as e:
                print(f"Error processing message: {e}")
                return {"status": "error", "reason": str(e)}

# Запуск сервера
if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=11111)