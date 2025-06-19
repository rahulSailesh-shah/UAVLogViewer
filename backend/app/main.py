from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import json
import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import base64
from app.log_processor import process_log_file
from app.llm_processor import LLMProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Create upload and processed directories if they don't exist
UPLOAD_DIR = Path("./uploads")
PROCESSED_DIR = Path("./processed")
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections and data
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_data: Dict[str, List[Dict]] = {}
        self.uploaded_files: Dict[str, str] = {}
        self.file_chunks: Dict[str, Dict[int, bytes]] = {}  # client_id -> {chunk_index: chunk_data}
        self.llm_processors: Dict[str, LLMProcessor] = {}  # client_id -> LLMProcessor
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}  # client_id -> conversation history

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_data[client_id] = []
        self.file_chunks[client_id] = {}
        self.conversation_histories[client_id] = [
            {"role": "assistant", "content": "Hi! I'm your ArduPilot flight data assistant. How can I help you analyze your flight logs today?"}
        ]
        await self.send_personal_message(
            json.dumps({
                "type": "system",
                "content": f"Welcome! Your client ID is: {client_id}",
                "timestamp": datetime.now().isoformat()
            }),
            client_id
        )

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_data:
            del self.client_data[client_id]
        if client_id in self.uploaded_files:
            try:
                # os.remove(self.uploaded_files[client_id])
                del self.uploaded_files[client_id]
            except Exception as e:
                logger.error(f"Error cleaning up file for client {client_id}: {e}")
        if client_id in self.file_chunks:
            del self.file_chunks[client_id]
        if client_id in self.llm_processors:
            del self.llm_processors[client_id]
        if client_id in self.conversation_histories:
            del self.conversation_histories[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str, exclude_client: str = None):
        for client_id, connection in self.active_connections.items():
            if client_id != exclude_client:
                await connection.send_text(message)

    def store_data(self, client_id: str, data: Dict):
        if client_id in self.client_data:
            self.client_data[client_id].append(data)
            logger.info(f"Stored data for client {client_id}. Current data count: {len(self.client_data[client_id])}")
        else:
            logger.warning(f"Attempted to store data for unknown client {client_id}")

    def store_file(self, client_id: str, file_path: str):
        self.uploaded_files[client_id] = file_path
        logger.info(f"Stored file path for client {client_id}: {file_path}")

    async def store_file_chunk(self, client_id: str, chunk_index: int, chunk_data: bytes, file_name: str):
        if client_id not in self.file_chunks:
            self.file_chunks[client_id] = {}
        self.file_chunks[client_id][chunk_index] = chunk_data
        logger.info(f"Stored chunk {chunk_index} for file {file_name} from client {client_id}")

    async def reconstruct_file(self, client_id: str, file_name: str, total_chunks: int):
        if client_id not in self.file_chunks:
            logger.error(f"No chunks found for client {client_id}")
            return None

        chunks = self.file_chunks[client_id]
        if len(chunks) != total_chunks:
            logger.error(f"Missing chunks for client {client_id}. Expected {total_chunks}, got {len(chunks)}")
            return None

        try:
            # Ensure directories exist
            UPLOAD_DIR.mkdir(exist_ok=True)
            PROCESSED_DIR.mkdir(exist_ok=True)
            logger.info(f"Ensured directories exist: {UPLOAD_DIR}, {PROCESSED_DIR}")

            # Create a unique filename using timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file_name)[1]
            unique_filename = f"{timestamp}{file_extension}"
            file_path = UPLOAD_DIR / unique_filename

            # Reconstruct the file
            with open(file_path, 'wb') as f:
                for i in range(total_chunks):
                    if i not in chunks:
                        raise ValueError(f"Missing chunk {i}")
                    f.write(chunks[i])

            logger.info(f"File reconstructed successfully: {file_path}")

            # Store the file path
            self.uploaded_files[client_id] = str(file_path)

            # Clean up chunks
            del self.file_chunks[client_id]

            # Send processing message
            await self.send_personal_message(
                json.dumps({
                    "type": "system",
                    "content": "Processing File",
                    "timestamp": datetime.now().isoformat()
                }),
                client_id
            )

            # Process the log file
            try:
                processed_file = await process_log_file(str(file_path), str(PROCESSED_DIR))
                logger.info(f"Log file processed successfully: {processed_file}")

                # Initialize LLM processor with the processed file
                self.llm_processors[client_id] = LLMProcessor(
                    raw_data_file=processed_file,
                    schema_file="scraper/schema.json",
                    db_path="chroma_db"
                )

                return str(file_path), processed_file
            except Exception as e:
                logger.error(f"Error processing log file: {e}")
                return str(file_path), None

        except Exception as e:
            logger.error(f"Error reconstructing file for client {client_id}: {e}")
            return None

    async def process_chat_message(self, client_id: str, message: str):
        """Process a chat message using the LLM processor"""
        if client_id not in self.llm_processors:
            await self.send_personal_message(
                json.dumps({
                    "type": "error",
                    "content": "Please upload a log file first before asking questions.",
                    "timestamp": datetime.now().isoformat()
                }),
                client_id
            )
            return

        try:
            # Send initial response message
            await self.send_personal_message(
                json.dumps({
                    "type": "chat",
                    "content": "Processing your question...",
                    "timestamp": datetime.now().isoformat()
                }),
                client_id
            )

            # Process the message and stream the response
            async for chunk in self.llm_processors[client_id].process_message(
                message,
                self.conversation_histories[client_id]
            ):
                await self.send_personal_message(
                    json.dumps({
                        "type": "chat",
                        "content": chunk,
                        "timestamp": datetime.now().isoformat()
                    }),
                    client_id
                )

            # Update conversation history
            self.conversation_histories[client_id].append(
                {"role": "user", "content": message}
            )

        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            await self.send_personal_message(
                json.dumps({
                    "type": "error",
                    "content": f"Error processing your message: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }),
                client_id
            )

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Welcome to UAV Log Viewer API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    logger.info(f"New WebSocket connection from client {client_id}")
    await manager.connect(websocket, client_id)
    try:
        while True:
            try:
                # Try to receive as text first
                data = await websocket.receive_text()
                logger.info(f"Received text message from client {client_id}")
                try:
                    message_data = json.loads(data)
                    message_data["timestamp"] = datetime.now().isoformat()
                    logger.info(f"Message type: {message_data.get('type')}")

                    if message_data.get("type") == "file_chunk":
                        logger.info(f"Received file chunk {message_data['content']['chunkIndex'] + 1}/{message_data['content']['totalChunks']} for file {message_data['content']['fileName']}")

                        # Decode base64 data
                        chunk_data = base64.b64decode(message_data['content']['data'])

                        # Store the chunk
                        await manager.store_file_chunk(
                            client_id,
                            message_data['content']['chunkIndex'],
                            chunk_data,
                            message_data['content']['fileName']
                        )

                        await manager.send_personal_message(
                            json.dumps({
                                "type": "acknowledgment",
                                "content": f"Received chunk {message_data['content']['chunkIndex'] + 1}/{message_data['content']['totalChunks']}",
                                "timestamp": datetime.now().isoformat()
                            }),
                            client_id
                        )
                    elif message_data.get("type") == "file_complete":
                        logger.info(f"File transfer complete for {message_data['content']['fileName']} ({message_data['content']['totalChunks']} chunks)")

                        # Reconstruct the file and process it
                        result = await manager.reconstruct_file(
                            client_id,
                            message_data['content']['fileName'],
                            message_data['content']['totalChunks']
                        )

                        if result:
                            file_path, processed_file = result
                            await manager.send_personal_message(
                                json.dumps({
                                    "type": "system",
                                    "content": f"File saved successfully: {os.path.basename(file_path)}",
                                    "timestamp": datetime.now().isoformat()
                                }),
                                client_id
                            )

                            if processed_file:
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "system",
                                        "content": f"Log file processed successfully: {os.path.basename(processed_file)}",
                                        "timestamp": datetime.now().isoformat()
                                    }),
                                    client_id
                                )
                            else:
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "error",
                                        "content": "Failed to process log file",
                                        "timestamp": datetime.now().isoformat()
                                    }),
                                    client_id
                                )
                        else:
                            await manager.send_personal_message(
                                json.dumps({
                                    "type": "error",
                                    "content": "Failed to save file",
                                    "timestamp": datetime.now().isoformat()
                                }),
                                client_id
                            )
                    elif message_data.get("type") == "chat":
                        # Process chat message with LLM
                        await manager.process_chat_message(
                            client_id,
                            message_data.get("content", "")
                        )
                    else:
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "acknowledgment",
                                "content": "Message received",
                                "original_message": message_data,
                                "timestamp": datetime.now().isoformat()
                            }),
                            client_id
                        )
                        await manager.broadcast(
                            json.dumps(message_data),
                            exclude_client=client_id
                        )

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from client {client_id}: {data}")
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "content": "Invalid message format. Please send valid JSON.",
                            "timestamp": datetime.now().isoformat()
                        }),
                        client_id
                    )

            except WebSocketDisconnect:
                logger.info(f"Client {client_id} disconnected")
                manager.disconnect(client_id)
                await manager.broadcast(
                    json.dumps({
                        "type": "system",
                        "content": f"Client {client_id} disconnected",
                        "timestamp": datetime.now().isoformat()
                    })
                )
                break

            except Exception as e:
                logger.error(f"Error processing message from client {client_id}: {str(e)}")
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error",
                        "content": f"Error processing message: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }),
                    client_id
                )

    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
        manager.disconnect(client_id)
