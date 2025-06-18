import json
import chromadb
from chromadb.utils import embedding_functions
import os

def prepare_documents_from_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            log_messages = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        print("Please make sure the JSON file from the scraper is in the same directory.")
        return [], [], []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from the file '{file_path}'.")
        return [], [], []

    ids = []
    documents = []
    metadatas = []

    for i, message in enumerate(log_messages):
        msg_name = message.get("MessageName", "Unknown")
        unique_id = f"log_msg_{i}_{msg_name}"

        fields_str_parts = []
        for field in message.get("Fields", []):
            field_name = field.get("FieldName", "")
            units = field.get("Units", "")
            desc = field.get("Description", "")
            fields_str_parts.append(f"- {field_name} ({units}): {desc}")

        fields_str = "\n".join(fields_str_parts)

        document_text = (
            f"Log Message: {msg_name}\n"
            f"Description: {message.get('Description', '')}\n"
            f"Fields:\n{fields_str}"
        )

        ids.append(unique_id)
        documents.append(document_text)

        metadatas.append({
            "MessageName": msg_name,
            "Description": message.get("Description", ""),
            "Fields": json.dumps(message.get("Fields", []))
        })

    return ids, documents, metadatas

def main():
    """
    Main function to load data, create embeddings, and store them in ChromaDB.
    """
    json_file = "backend/scraper/schema.json"
    ids, documents, metadatas = prepare_documents_from_json(json_file)

    if not documents:
        print("No documents were prepared. Exiting.")
        return

    print(f"Successfully prepared {len(documents)} documents for embedding.")
    db_path = "chroma_db"
    if not os.path.exists(db_path):
        os.makedirs(db_path)

    client = chromadb.PersistentClient(path=db_path)

    embedding_model_name = "all-MiniLM-L6-v2"
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model_name
    )

    collection_name = "ardupilot_logs"
    print(f"Creating or loading ChromaDB collection: '{collection_name}'")
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"} # Use cosine distance for similarity
    )

    print("Adding documents to the collection... (This may take a moment)")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print("Documents have been successfully added to the ChromaDB collection.")

if __name__ == "__main__":
    main()
