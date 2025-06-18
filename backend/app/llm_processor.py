import os
import json
import chromadb
from chromadb.utils import embedding_functions
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List, Dict, Any
import logging
from dotenv import load_dotenv
import asyncio

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTROPIC key environment variable is not set")

logger = logging.getLogger(__name__)

class ChromaDBVectorStore:
    def __init__(self, db_path="chroma_db", collection_name="ardupilot_logs"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_collection(
            name=collection_name,
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        )

    def similarity_search(self, query: str, k: int = 5) -> Dict[str, Any]:
        """Search for similar messages in ChromaDB"""
        return self.collection.query(
            query_texts=[query],
            n_results=k,
            include=["metadatas", "documents", "distances"]
        )

class DataFetcher:
    def __init__(self, raw_data_file: str, schema_file: str):
        self.raw_data_file = raw_data_file
        self.schema_file = schema_file
        self.raw_data = self._load_raw_data()
        self.schemas = self._load_schemas()

    def _load_raw_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load raw data from JSON file"""
        try:
            with open(self.raw_data_file, 'r') as f:
                data = json.load(f)
                return data.get("messages", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading raw data: {e}")
            return {}

    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load schemas and index by MessageName"""
        try:
            with open(self.schema_file, 'r') as f:
                schemas = json.load(f)
                return {schema["MessageName"]: schema for schema in schemas}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading schemas: {e}")
            return {}

    def fetch_data(self, message_types: List[str], required_fields: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch data and schemas for requested message types"""
        result = {}

        for msg_type in message_types:
            # Get schema information
            schema = self.schemas.get(msg_type, {
                "MessageName": msg_type,
                "Description": "Schema not found",
                "Fields": []
            })

            entries = self.raw_data.get(msg_type, [])

            if required_fields:
                filtered_entries = []
                for entry in entries:
                    filtered_entry = {field: entry.get(field)
                                      for field in required_fields
                                      if field in entry}
                    filtered_entries.append(filtered_entry)
                entries = filtered_entries

            result[msg_type] = {
                "schema": schema,
                "data": entries
            }

        return result

class AgentState(TypedDict):
    user_query: str
    conversation_history: List[Dict[str, str]]  # Stores chat history
    retrieved_messages: Optional[List[Dict[str, Any]]]
    selected_messages: Optional[List[Dict[str, Any]]]
    fetched_data: Optional[Dict[str, Dict[str, Any]]]
    answer: Optional[str]  # Final answer to the user

def retrieve_node(state: AgentState, vector_store: ChromaDBVectorStore) -> dict:
    results = vector_store.similarity_search(state["user_query"], k=5)

    retrieved = []
    for metadata in results["metadatas"][0]:
        try:
            message = {
                "MessageName": metadata["MessageName"],
                "Description": metadata["Description"],
                "Fields": json.loads(metadata["Fields"])
            }
            retrieved.append(message)
        except (KeyError, json.JSONDecodeError):
            continue

    return {"retrieved_messages": retrieved}

def analyze_node(state: AgentState) -> dict:
    prompt_template = """
    <task>
    Analyze the user query and available message definitions to determine:
    1. ALL relevant message types (MessageName)
    2. Specific fields needed from each message type to answer the query

    Return a JSON list of objects where each object has:
    - "message_type": The exact MessageName (e.g. "ACC")
    - "required_fields": List of exact field names needed from this message (e.g. ["TimeUS", "AccX"])
    </task>

    <user_query>
    {query}
    </user_query>

    <available_messages>
    {messages}
    </available_messages>

    <conversation_history>
    {history}
    </conversation_history>

    <instructions>
    - Respond ONLY in JSON format with a list of objects
    - Each object MUST have keys: "message_type" and "required_fields"
    - "message_type" must be the exact MessageName value
    - "required_fields" must be a list of exact field names (or empty list if no specific fields)
    - Consider the conversation history when determining relevance
    - Include ALL relevant messages needed to answer the query
    - Select fields ONLY when explicitly mentioned in the query
    - If a message is needed but no specific fields are requested, include the message with empty required_fields
    - Order messages by relevance to the query
    </instructions>
    """

    prompt = ChatPromptTemplate.from_template(prompt_template)
    model = ChatAnthropic(
        model_name="claude-3-sonnet-20240229",
        temperature=0,
        max_tokens=2048,
        anthropic_api_key=ANTHROPIC_API_KEY
    )

    formatted_messages = []
    for msg in state["retrieved_messages"]:
        fields = "\n".join(
            [f"  • {field['FieldName']} ({field['Units']}): {field['Description']}"
             for field in msg["Fields"]]
        )
        formatted_messages.append(
            f"### {msg['MessageName']} ###\n"
            f"Description: {msg['Description']}\n"
            f"Fields:\n{fields}"
        )

    history_str = "\n".join(
        [f"{msg['role']}: {msg['content']}"
         for msg in state["conversation_history"]]
    ) if state.get("conversation_history") else "No history"

    chain = prompt | model | JsonOutputParser()
    response = chain.invoke({
        "query": state["user_query"],
        "messages": "\n\n".join(formatted_messages),
        "history": history_str
    })

    selected_messages = []
    if isinstance(response, list):
        for item in response:
            if "message_type" in item and "required_fields" in item:
                selected_messages.append({
                    "message_type": item["message_type"],
                    "required_fields": item["required_fields"]
                })

    return {"selected_messages": selected_messages}

def fetch_data_node(state: AgentState, data_fetcher: DataFetcher) -> dict:
    if not state.get("selected_messages"):
        return {"fetched_data": {}}

    message_types = [msg["message_type"] for msg in state["selected_messages"]]

    field_requirements = {}
    for msg in state["selected_messages"]:
        field_requirements[msg["message_type"]] = msg["required_fields"]

    fetched_data = data_fetcher.fetch_data(message_types, [])

    for msg_type, data_info in fetched_data.items():
        required_fields = field_requirements.get(msg_type, [])

        if required_fields:
            filtered_entries = []
            for entry in data_info["data"]:
                filtered_entry = {field: entry.get(field)
                                 for field in required_fields
                                 if field in entry}
                filtered_entries.append(filtered_entry)
            data_info["data"] = filtered_entries

    return {"fetched_data": fetched_data}

def analyze_data_node(state: AgentState) -> dict:
    if not state.get("fetched_data"):
        return {"answer": "I couldn't find relevant data to answer your question."}

    context_parts = [
        f"# Conversation History\n" + "\n".join(
            [f"{msg['role']}: {msg['content']}"
             for msg in state["conversation_history"]]
        ) if state.get("conversation_history") else "# No conversation history",

        f"\n\n# User Query\n{state['user_query']}",

        "\n\n# Relevant Data Schemas and Samples"
    ]

    for msg_type, data_info in state["fetched_data"].items():
        schema = data_info["schema"]
        entries = data_info["data"]

        context_parts.append(f"\n## {msg_type} Schema")
        context_parts.append(f"Description: {schema.get('Description', 'No description available')}")
        context_parts.append("Fields:")
        for field in schema.get("Fields", []):
            context_parts.append(f"- {field['FieldName']} ({field.get('Units', '')}): {field['Description']}")

        context_parts.append(f"\n### {msg_type} Data Samples (showing {min(3, len(entries))} of {len(entries)} entries)")
        if entries:
            for i, entry in enumerate(entries[:3]):
                context_parts.append(f"Sample {i+1}:")
                for key, value in entry.items():
                    context_parts.append(f"  {key}: {value}")
        else:
            context_parts.append("No data available for this message type")

    context = "\n".join(context_parts)

    prompt_template = """
    <role>
    You are ArduPilot Analyst, an expert assistant for analyzing ArduPilot flight data.
    You help users understand flight logs, answer questions about flight performance,
    and provide insights based on telemetry data.
    </role>

    <context>
    {context}
    </context>

    <instructions>
    1. Consider the entire conversation history for context
    2. Analyze the data samples that are relevant to the current query
    3. Provide a concise but comprehensive answer to the user's question
    4. When mentioning values, include units from the schema
    5. If the data is insufficient, explain what's missing
    6. Structure your response:
       - Start with a direct answer
       - Provide supporting evidence from the data
       - Note any limitations or data quality issues
       - Suggest follow-up questions when appropriate
    7. Maintain a friendly, professional tone
    </instructions>

    Now provide your response to the user:
    """

    prompt = ChatPromptTemplate.from_template(prompt_template)
    model = ChatAnthropic(
        model_name="claude-3-opus-20240229",
        temperature=0.3,
        max_tokens=2000,
        anthropic_api_key=ANTHROPIC_API_KEY
    )
    chain = prompt | model | StrOutputParser()

    answer = chain.invoke({
        "context": context
    })

    return {"answer": answer}

def update_history_node(state: AgentState) -> dict:
    """Update conversation history with the latest exchange"""
    new_history = state["conversation_history"] + [
        {"role": "user", "content": state["user_query"]},
        {"role": "assistant", "content": state["answer"]}
    ]
    return {"conversation_history": new_history}

class LLMProcessor:
    def __init__(self, raw_data_file: str, schema_file: str, db_path: str = "chroma_db"):
        self.vector_store = ChromaDBVectorStore(db_path=db_path)
        self.data_fetcher = DataFetcher(raw_data_file, schema_file)
        self.workflow = self._create_workflow()

    def _create_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("retrieve", lambda state: retrieve_node(state, self.vector_store))
        workflow.add_node("analyze", analyze_node)
        workflow.add_node("fetch_data", lambda state: fetch_data_node(state, self.data_fetcher))
        workflow.add_node("analyze_data", analyze_data_node)
        workflow.add_node("update_history", update_history_node)

        workflow.set_entry_point("retrieve")

        workflow.add_edge("retrieve", "analyze")
        workflow.add_edge("analyze", "fetch_data")
        workflow.add_edge("fetch_data", "analyze_data")
        workflow.add_edge("analyze_data", "update_history")
        workflow.add_edge("update_history", END)

        return workflow.compile()

    async def process_message(self, message: str, conversation_history: List[Dict[str, str]]) -> str:
        """Process a message and return the response"""
        state = {
            "user_query": message,
            "conversation_history": conversation_history,
            "retrieved_messages": None,
            "selected_messages": None,
            "fetched_data": None,
            "answer": None
        }

        try:
            # Run the workflow and get the final state
            final_state = await self.workflow.ainvoke(state)

            # Return the complete answer
            if final_state.get("answer"):
                yield final_state["answer"]
            else:
                yield "I couldn't generate a response for your query."

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            yield f"I encountered an error while processing your message: {str(e)}"
