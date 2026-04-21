import chromadb
from chromadb.utils import embedding_functions
import asyncio
import uuid
from datetime import datetime

chroma_client = chromadb.PersistentClient(path="./bot_memory")

sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

collection = chroma_client.get_or_create_collection(
    name="discord_chat_history", 
    embedding_function=sentence_transformer_ef
)

async def save_to_memory(user_id: str, role: str, text: str):

    def _save():
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        collection.add(
            documents=[text],
            metadatas=[{"user_id": str(user_id), "role": role, "time": timestamp}],
            ids=[doc_id]
        )
    await asyncio.to_thread(_save)

async def recall_memory(user_id: str, query: str, n_results: int = 3) -> str:

    def _search():
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": str(user_id)}
        )
        return results

    results = await asyncio.to_thread(_search)
    
    if not results['documents'] or not results['documents'][0]:
        return ""

    context_lines = []
    for i, doc in enumerate(results['documents'][0]):
        role = results['metadatas'][0][i]['role']
        time = results['metadatas'][0][i]['time']
        sender = "Користувач" if role == "user" else "Ти (Бот)"
        context_lines.append(f"[{time}] {sender} сказав: {doc}")
        
    return "\n".join(context_lines)