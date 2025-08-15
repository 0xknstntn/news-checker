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


def send_msg(msg):
        message = {
                "input": msg,
                "chat_id": "12345678",
                "session_id": f"12345678_session"
        }

        push_message(json.dumps(message, ensure_ascii=False))

# Запуск сервера
if __name__ == "__main__":
        while True:
                send_msg(input("msg> "))