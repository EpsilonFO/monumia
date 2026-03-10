#!/usr/bin/env python3
"""
Script to store embeddings in a vector database for RAG (Retrieval-Augmented Generation).
Uses ChromaDB as the vector database and Sentence Transformers for embeddings.
"""

import os
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from typing import List

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Initialize embedding function using Sentence Transformers
# Using 'all-MiniLM-L6-v2' model which is efficient and effective
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Create or get a collection for storing embeddings
collection_name = "rag_embeddings"
try:
    collection = chroma_client.get_collection(name=collection_name)
    print(f"Using existing collection: {collection_name}")
except:
    collection = chroma_client.create_collection(
        name=collection_name,
        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    )
    print(f"Created new collection: {collection_name}")

# Sample documents to chunk and embed
documents = [
    "The capital of France is Paris. Paris is known for the Eiffel Tower.",
    "Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data.",
    "Python is a popular programming language created by Guido van Rossum in 1991.",
    "Deep learning uses neural networks with many layers to model complex patterns in data."
]

# Function to chunk documents (simple implementation)
def chunk_document(document: str, chunk_size: int = 100) -> List[str]:
    """Split document into chunks of approximately chunk_size characters."""
    words = document.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        current_chunk.append(word)
        current_length += len(word) + 1  # +1 for space
        
        if current_length >= chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_length = 0
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

# Process documents and store embeddings
def store_embeddings(documents: List[str]):
    """Chunk documents and store their embeddings in the vector database."""
    all_chunks = []
    all_ids = []
    all_metadata = []
    
    for doc_id, document in enumerate(documents):
        chunks = chunk_document(document)
        
        for chunk_id, chunk in enumerate(chunks):
            chunk_id_str = f"doc_{doc_id}_chunk_{chunk_id}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id_str)
            all_metadata.append({
                "document_id": doc_id,
                "chunk_id": chunk_id,
                "chunk_length": len(chunk)
            })
    
    # Add embeddings to the collection
    collection.add(
        documents=all_chunks,
        metadatas=all_metadata,
        ids=all_ids
    )
    
    print(f"Stored {len(all_chunks)} chunks in the vector database.")
    return len(all_chunks)

# Query the vector database
def query_vector_db(query_text: str, top_k: int = 3):
    """Query the vector database for similar chunks."""
    results = collection.query(
        query_texts=[query_text],
        n_results=top_k
    )
    
    print(f"\nQuery: '{query_text}'")
    print(f"Top {top_k} results:")
    for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"\nResult {i+1}:")
        print(f"  Content: {doc}")
        print(f"  Metadata: {meta}")
    
    return results

if __name__ == "__main__":
    # Store embeddings
    num_chunks = store_embeddings(documents)
    
    # Example queries
    query_vector_db("What is the capital of France?")
    query_vector_db("Tell me about machine learning")
    query_vector_db("Who created Python?")
    
    print(f"\nRAG system ready with {num_chunks} document chunks!")