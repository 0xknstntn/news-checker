from langchain.schema import BaseChatMessageHistory
from pymongo import MongoClient
from langchain_core.messages.base import messages_to_dict
from langchain_core.messages.utils import messages_from_dict
from datetime import datetime, timezone

class MongoChatMessageHistory(BaseChatMessageHistory):
        def __init__(self, session_id: str, collection):
                self.session_id = session_id
                self.collection = collection

        @property
        def messages(self):
                try:
                        docs = list(self.collection.find(
                                {"session_id": self.session_id},
                                {"_id": 0}
                        ).sort("timestamp", -1).limit(20))
                        return messages_from_dict([doc["message"] for doc in docs])
                except Exception as e:
                        print(f"Error getting messages: {e}")
                        return []
                

        def add_message(self, message):
                try:
                        self.collection.insert_one({
                                "session_id": self.session_id,
                                "message": messages_to_dict([message])[0]
                        })
                except Exception as e:
                        print(f"Error adding message: {e}")

        def clear(self):
                try:
                        self.collection.delete_many({"session_id": self.session_id})
                except Exception as e:
                        print(f"Error clearing messages: {e}")

class MongoSessionStepMemory:
        def __init__(self, collection):
                self.collection = collection

        def add_step(self, session_id: str, description: str):
                try:
                        self.collection.insert_one({
                                "session_id": session_id,
                                "description": description,
                                "timestamp": datetime.now(timezone.utc)
                        })
                except Exception as e:
                        print(f"Error adding step: {e}")

        def get_history(self, session_id: str) -> str:
                try:
                        steps = list(
                        self.collection.find(
                                {"session_id": session_id},
                                {"_id": 0, "description": 1}
                        ).sort("timestamp", -1).limit(20)
                        )
                        return "\n".join([step["description"] for step in steps])
                except Exception as e:
                        print(f"Error getting history: {e}")
                        return ""

        def clear(self, session_id: str):
                try:
                        self.collection.delete_many({"session_id": session_id})
                except Exception as e:
                        print(f"Error clearing steps: {e}")

        def clear_all(self):
                try:
                        self.collection.delete_many({})
                except Exception as e:
                        print(f"Error clearing all steps: {e}")

        def get_steps(self, session_id: str) -> list:
                try:
                        steps = list(
                                self.collection.find(
                                        {"session_id": session_id},
                                        {"_id": 0, "description": 1}
                                ).sort("timestamp", -1).limit(20)
                        )
                        return [step["description"] for step in steps]
                except Exception as e:
                        print(f"Error getting steps: {e}")
                        return []
