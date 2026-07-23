import os
import ollama

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# Configure the ollama client
client = ollama.AsyncClient(host=OLLAMA_BASE_URL)

async def generate_embedding(text: str) -> list[float]:
    """Generates a vector embedding for the given text using nomic-embed-text."""
    if not text or not text.strip():
        return []
        
    try:
        response = await client.embeddings(
            model=EMBEDDING_MODEL,
            prompt=text
        )
        return response.get('embedding', [])
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return []
