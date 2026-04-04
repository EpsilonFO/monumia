"""
RAG with Supabase Storage Vectors (vecs library).

Setup (one-time):
  1. Enable pgvector in Supabase: Dashboard > Database > Extensions > vector
  2. pip install vecs mistralai python-dotenv

Requires a .env.rag file in test_rag/:
  DB_CONNECTION=postgresql://postgres:<password>@<host>:5432/postgres
  MISTRAL_API_KEY=...

The DB_CONNECTION is the direct Postgres URL from:
  Supabase Dashboard > Project Settings > Database > Connection string (URI mode)
"""

import os
import uuid
from dotenv import load_dotenv
from mistralai import Mistral
import vecs

load_dotenv(".env.rag")

DB_CONNECTION = os.environ["DB_CONNECTION"]
MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]

EMBEDDING_DIM = 1024  # mistral-embed output dimension
CHUNK_SIZE = 500
OVERLAP = 50
TOP_K = 5
COLLECTION_NAME = "document_chunks"


def load_document(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    return {
        "document_id": str(uuid.uuid4()),
        "filename": filepath,
        "content": content,
    }


def chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += CHUNK_SIZE - OVERLAP
    return chunks


def create_chunks_with_metadata(document: dict) -> list[dict]:
    raw_chunks = chunk_text(document["content"])
    return [
        {
            "chunk_id": str(uuid.uuid4()),
            "text": chunk,
            "metadata": {
                "document_id": document["document_id"],
                "filename": document["filename"],
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            },
        }
        for i, chunk in enumerate(raw_chunks)
    ]


def get_embedding(text: str) -> list[float]:
    response = mistral_client.embeddings.create(
        model="mistral-embed",
        inputs=text,
    )
    return response.data[0].embedding


def index_documents(data_dir: str, collection) -> dict[str, str]:
    """Index all documents from data_dir. Returns document_id -> content map."""
    print("Clearing existing chunks...")
    # Delete all records by upserting with an empty list after deleting
    # vecs doesn't have a truncate, so we recreate the collection
    vx.delete_collection(COLLECTION_NAME)
    fresh_collection = vx.get_or_create_collection(
        name=COLLECTION_NAME, dimension=EMBEDDING_DIM
    )

    documents_store = {}
    records = []

    for filename in os.listdir(data_dir):
        filepath = os.path.join(data_dir, filename)
        doc = load_document(filepath)
        print(f"  Indexing {filename} ({doc['document_id'][:8]}...)")
        chunks = create_chunks_with_metadata(doc)

        for chunk in chunks:
            embedding = get_embedding(chunk["text"])
            records.append(
                (
                    chunk["chunk_id"],  # unique id
                    embedding,  # vector
                    {  # metadata
                        "document_id": chunk["metadata"]["document_id"],
                        "filename": chunk["metadata"]["filename"],
                        "chunk_index": chunk["metadata"]["chunk_index"],
                        "total_chunks": chunk["metadata"]["total_chunks"],
                        "text": chunk["text"],
                    },
                )
            )

        documents_store[doc["document_id"]] = doc["content"]

    print(f"  Upserting {len(records)} chunks...")
    fresh_collection.upsert(records=records)

    print("  Creating index...")
    fresh_collection.create_index(
        method=vecs.IndexMethod.hnsw,
        measure=vecs.IndexMeasure.cosine_distance,
    )

    print(f"  Indexed {len(documents_store)} document(s)")
    return documents_store, fresh_collection


def search_and_get_full_document(
    query: str, documents_store: dict[str, str], collection
) -> str:
    query_embedding = get_embedding(query)

    results = collection.query(
        data=query_embedding,
        limit=TOP_K,
        include_metadata=True,
        include_value=True,
        measure="cosine_distance",
    )

    doc_id_to_filename: dict[str, str] = {}
    for _chunk_id, _distance, metadata in results:
        doc_id = metadata["document_id"]
        doc_id_to_filename[doc_id] = metadata["filename"]

    print(f"Chunks trouvés dans {len(doc_id_to_filename)} document(s) unique(s)")

    sections = []
    for doc_id, filename in doc_id_to_filename.items():
        name = os.path.splitext(os.path.basename(filename))[0]
        sections.append(f"# {name}\n\n{documents_store[doc_id]}")

    return "\n\n---\n\n".join(sections)


def answer_with_context(question: str, context: str) -> str:
    prompt = f"""
    On cherche à répondre à la question suivante :
    Question: {question}

    On a exécuté un RAG sur une base de documents décrivant des aides à la rénovation du patrimoine, et on a trouvé les documents suivants qui semblent pertinents pour répondre à la question :
    {context}
    A chaque fois que tu vois un titre (une ligne qui commence par #), tu peux considérer que c'est une nouvelle section qui parle d'un sujet différent.
    Je veux que tu m'expliques rapidement, en te basant sur les sections trouvées, pourquoi l'aide décrite dans chaque section est pertinente pour répondre à la question.
    Réponse:
    """
    response = mistral_client.chat.complete(
        model="ministral-8b-latest",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    mistral_client = Mistral(api_key=MISTRAL_API_KEY)

    with vecs.create_client(DB_CONNECTION) as vx:
        collection = vx.get_or_create_collection(
            name=COLLECTION_NAME, dimension=EMBEDDING_DIM
        )

        data_dir = "data/aides_notion/"
        documents_store, collection = index_documents(data_dir, collection)

        # question = "Quelles aides pour des rénovations sur la toiture de mon château privé inscrit, à Emalleville en Normandie dans l'Eure ?"
        # doc_complet = search_and_get_full_document(question, documents_store, collection)

        # with open("resultat_recherche.md", "w", encoding="utf-8") as f:
        #     f.write(doc_complet)

        # answer = answer_with_context(question, doc_complet)
        # with open("answer.md", "w", encoding="utf-8") as f:
        #     f.write(answer)

        # print("\nQuestion:", question)
        # print("\nRéponse:", answer)
