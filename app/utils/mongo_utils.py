import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class MongoDBManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.chat_collection: Optional[AsyncIOMotorCollection] = None
        self.data_collection: Optional[AsyncIOMotorCollection] = None
        self.is_connected = False
        
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.db_name = os.getenv("MONGO_DB_NAME", "EZ")
        self.chat_collection_name = os.getenv("MONGO_CHAT_COLLECTION_NAME", "chat")
        self.data_collection_name = os.getenv("MONGO_DATA_COLLECTION_NAME", "upload_data")

    async def connect(self):
        if not self.mongo_uri:
            print("MongoDB URI not found in environment variables. Running in memory-only mode.")
            return False
        
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            await self.client.admin.command('ping')
            
            self.database = self.client[self.db_name]
            self.chat_collection = self.database[self.chat_collection_name]
            self.data_collection = self.database[self.data_collection_name]
            
            await self._create_indexes()
            self.is_connected = True
            print(f"Successfully connected to MongoDB database: {self.db_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"Failed to connect to MongoDB: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            print(f"Unexpected error connecting to MongoDB: {e}")
            self.is_connected = False
            return False

    async def _create_indexes(self):
        try:
            await self.chat_collection.create_index([("session_id", 1), ("document_filename", 1)])
            await self.chat_collection.create_index([("timestamp", -1)])
            await self.data_collection.create_index([("filename", 1)])
            await self.data_collection.create_index([("upload_timestamp", -1)])
        except Exception as e:
            print(f"Warning: Failed to create indexes: {e}")

    async def disconnect(self):
        if self.client:
            self.client.close()
            self.is_connected = False
            print("Disconnected from MongoDB")

    def _serialize_message(self, message: BaseMessage) -> Dict[str, Any]:
        return {
            "type": message.__class__.__name__,
            "content": message.content,
            "additional_kwargs": getattr(message, 'additional_kwargs', {})
        }

    def _deserialize_message(self, data: Dict[str, Any]) -> BaseMessage:
        message_type = data.get("type", "HumanMessage")
        content = data.get("content", "")
        additional_kwargs = data.get("additional_kwargs", {})
        
        if message_type == "HumanMessage":
            return HumanMessage(content=content, additional_kwargs=additional_kwargs)
        elif message_type == "AIMessage":
            return AIMessage(content=content, additional_kwargs=additional_kwargs)
        else:
            return HumanMessage(content=content, additional_kwargs=additional_kwargs)

    async def store_document(self, filename: str, text: str, summary: Optional[str] = None, file_path: Optional[str] = None) -> bool:
        if not self.is_connected:
            print("MongoDB not connected. Document not stored.")
            return False
        
        try:
            document_data = {
                "filename": filename,
                "text": text,
                "summary": summary,
                "file_path": file_path,
                "upload_timestamp": datetime.utcnow(),
                "text_length": len(text)
            }
            
            await self.data_collection.replace_one(
                {"filename": filename},
                document_data,
                upsert=True
            )
            print(f"Document '{filename}' stored in MongoDB")
            return True
            
        except Exception as e:
            print(f"Error storing document in MongoDB: {e}")
            return False

    async def get_document(self, filename: str) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        
        try:
            document = await self.data_collection.find_one({"filename": filename})
            return document
        except Exception as e:
            print(f"Error retrieving document from MongoDB: {e}")
            return None

    async def store_chat_history(self, session_id: str, document_filename: str, chat_history: List[BaseMessage]) -> bool:
        if not self.is_connected:
            return False
        
        try:
            serialized_history = [self._serialize_message(msg) for msg in chat_history]
            
            chat_data = {
                "session_id": session_id,
                "document_filename": document_filename,
                "chat_history": serialized_history,
                "timestamp": datetime.utcnow(),
                "message_count": len(chat_history)
            }
            
            await self.chat_collection.replace_one(
                {"session_id": session_id, "document_filename": document_filename},
                chat_data,
                upsert=True
            )
            return True
            
        except Exception as e:
            print(f"Error storing chat history in MongoDB: {e}")
            return False

    async def get_chat_history(self, session_id: str, document_filename: str) -> Optional[List[BaseMessage]]:
        if not self.is_connected:
            return None
        
        try:
            chat_data = await self.chat_collection.find_one({
                "session_id": session_id,
                "document_filename": document_filename
            })
            
            if not chat_data or "chat_history" not in chat_data:
                return None
            
            return [self._deserialize_message(msg_data) for msg_data in chat_data["chat_history"]]
            
        except Exception as e:
            print(f"Error retrieving chat history from MongoDB: {e}")
            return None

    async def clear_chat_history(self, session_id: str, document_filename: str) -> bool:
        if not self.is_connected:
            return False
        
        try:
            await self.chat_collection.delete_one({
                "session_id": session_id,
                "document_filename": document_filename
            })
            return True
        except Exception as e:
            print(f"Error clearing chat history from MongoDB: {e}")
            return False

    async def get_recent_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.is_connected:
            return []
        
        try:
            cursor = self.data_collection.find({}).sort("upload_timestamp", -1).limit(limit)
            documents = await cursor.to_list(length=limit)
            return documents
        except Exception as e:
            print(f"Error retrieving recent documents: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_connected:
            return {"status": "disconnected", "message": "MongoDB not connected"}
        
        try:
            await self.client.admin.command('ping')
            doc_count = await self.data_collection.count_documents({})
            chat_count = await self.chat_collection.count_documents({})
            
            return {
                "status": "healthy",
                "database": self.db_name,
                "documents_stored": doc_count,
                "chat_sessions": chat_count,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

mongo_manager = MongoDBManager()

async def init_mongodb():
    await mongo_manager.connect()

async def cleanup_mongodb():
    await mongo_manager.disconnect() 