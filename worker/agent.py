from fastapi import FastAPI, Request, Response, HTTPException
import requests
import json
import os
from pymongo import MongoClient
from datetime import datetime, timedelta
import re
import asyncio
import redis.asyncio as aioredis
import uuid
from typing import Dict, List, Optional, Any, Union
from dotenv import load_dotenv
import warnings
import signal

from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from langchain.tools import BaseTool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.chains import LLMChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel, Field

from .tools import get_tools
from .prompts import get_prompt
from .utils import remove_markdown
from .memory import MongoChatMessageHistory, MongoSessionStepMemory
from .response import send_response
from .callback import PrettyVerboseCallbackHandler

try:
        from langchain._api.deprecation import LangChainDeprecationWarning
except ImportError:
        LangChainDeprecationWarning = UserWarning

warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

load_dotenv()

CONCURRENT_TASKS = 5

chat_model = ChatOpenAI(
        model_name="gpt-4.1",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.5,
)

tools = get_tools()

agent = create_openai_functions_agent(
        llm=chat_model,
        tools=tools,
        prompt=get_prompt()
)

mongo_client = None

def get_mongo_client():
        global mongo_client
        if mongo_client is None:
                mongo_client = MongoClient(os.environ.get("MONGODB_URI"))
        return mongo_client

def get_conversation_memory(chat_id):
        session_id = str(chat_id)
        
        client = get_mongo_client()

        return ConversationBufferMemory(
                memory_key="chat_history",
                output_key="output",
                return_messages=True,
                chat_memory=MongoChatMessageHistory(
                        session_id=chat_id,
                        collection=client[os.getenv("MONGODB_KEY")]["chat_history"]
                )
        )

sessions_memory = MongoSessionStepMemory(get_mongo_client()[os.getenv("MONGODB_KEY")]["step_memory_sessions"])

async def handle_message(message):
        print(f"New message received from handle_message: {message}")
        try:
                message = json.loads(message)
                
                memory = get_conversation_memory(message["chat_id"])

                agent_executor = AgentExecutor(
                        agent=agent,
                        tools=tools,
                        memory=memory,
                        verbose=False,
                        return_intermediate_steps=True,
                        callbacks=[PrettyVerboseCallbackHandler()]
                )

                agent_input = {
                        "user": message['input']
                }

                response = await agent_executor.ainvoke(agent_input)
                ai_response = response["output"]
                clean_response = remove_markdown(ai_response)
                
                """ Custom send """
                await send_response(clean_response, message["chat_id"])

                # === For testing ===
                # print("clean_response", clean_response)
                # return clean_response

        except Exception as e:
                print(f"Error processing message: {e}")
                # return {"status": "error", "reason": str(e)}


async def redis_listener(queue, stop_event):
        try:
                r = aioredis.Redis(host=os.getenv("REDIS_HOST"), port=6379, db=0)
                print("Redis listener started")
                while not stop_event.is_set():
                        try:
                                _, message = await asyncio.wait_for(
                                        r.brpop(os.getenv("REDIS_QUEUE_KEY")), timeout=1
                                )
                                print(f"New message received from redis: {message}")
                                await queue.put(message)
                        except asyncio.TimeoutError:
                                continue
        except asyncio.CancelledError:
                print("Redis listener cancelled")
        except Exception as e:
                print(f"Redis listener error: {e}")
                await asyncio.sleep(1)


async def worker(queue, stop_event):
        print("Worker started")
        while not stop_event.is_set():
                try:
                        message = await asyncio.wait_for(queue.get(), timeout=1)
                        try:
                                print(f"New message received from queue: {message}")
                                await handle_message(message.decode('utf-8'))
                        except Exception as e:
                                print(f"Error in handle_message: {e}")
                        finally:
                                queue.task_done()
                except asyncio.TimeoutError:
                        continue
                except Exception as e:
                        print(f"Worker error: {e}")

async def main():
        queue = asyncio.Queue()
        stop_event = asyncio.Event()

        tasks = []
        tasks.append(asyncio.create_task(redis_listener(queue, stop_event)))
        for _ in range(CONCURRENT_TASKS):
                tasks.append(asyncio.create_task(worker(queue, stop_event)))

        # Функция для корректного завершения
        def shutdown():
                print("Shutdown signal received!")
                stop_event.set()

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, shutdown)
        loop.add_signal_handler(signal.SIGTERM, shutdown)

        await stop_event.wait()  # ждать сигнала
        print("Stop event set, shutting down tasks...")

        # Корректно отменяем задачи
        for t in tasks:
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("All tasks shut down gracefully.")

def handle_exception(loop, context):
        print("GLOBAL EXCEPTION:", context)

if __name__ == "__main__":
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)
        loop.run_until_complete(main())
        print("PROCESS EXITED!!!")
