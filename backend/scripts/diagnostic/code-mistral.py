import os
import base64
import fitz
import numpy as np
from mistralai import Mistral
from dotenv import load_dotenv

# Charger la clé API
load_dotenv()
api_key = os.environ.get("MISTRAL_API_KEY")
embeddings = np.array([])


def chunk_text(file_path):
    chunk_size = 2048
    overlap = 256
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    if len(text) < chunk_size:
        chunks = [text]
    else:
        chunks = [text[:chunk_size]]
        for i in range(chunk_size, len(text), chunk_size):
            if i + chunk_size + overlap > len(text):
                chunks.append(text[i-overlap:])
            else:
                chunks.append(text[i-overlap:i+chunk_size+overlap])
    print(f"len(chunks): {len(chunks)}")
    return chunks

def embed_text(text):
    # Initialiser le client Mistral avec Pixtral-12B
    model = "mistral-embed"
    client = Mistral(api_key=api_key)

    embeddings_batch_response = client.embeddings.create(
        model=model,
        inputs=text,
    )
    return embeddings_batch_response.data[0].embedding

def get_embeddings(chunks):
    return np.array([embed_text(chunk) for chunk in chunks])

def euclidian_distance(vec1, vec2):
    return np.linalg.norm(vec1 - vec2)

def answer_with_context(question, chunks, embeddings):
    question_embedded = get_embeddings([question])
    distances = [euclidian_distance(question_embedded, embedding) for embedding in embeddings]
    top_k_indices = []
    for i in range(len(distances)):
        if distances[i] > 0.6:
            top_k_indices.append((i, distances[i]))
            if len(top_k_indices) >= 3:
                break

    context = "\n".join([chunks[i] for i in top_k_indices])
    model = "ministral-8b-latest"
    client = Mistral(api_key=api_key)

    # Envoyer le contenu corrigé au modèle Ministral-8B
    chat_response = client.chat.complete(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
Tu vas devoir faire une liste de toutes les aides de l'Etat, des départements, régions, ou de fondations pour subventionner des projets de rénovation du patrimoine publique ou privé auquel le bien suivant a droit :
{question}
Tu devras te baser sur les connaissances suivantes pour faire cette liste :
{context}
Des informations larges comme "il doit y avoir des aides pour les bâtiments classés monuments historiques" ne sont pas acceptables, tu dois être précis et donner des noms d'aides concrets.
Donne-moi des noms d'aides, des montants, des conditions d'éligibilité, et des liens vers les sites officiels si disponibles.
"""
                    }
                ]
            }
        ]
    )

    # Sauvegarder le texte corrigé
    with open("data/aides_notion/answer.md", "w", encoding="utf-8") as f:
        f.write(chat_response.choices[0].message.content)

if __name__ == "__main__":
    # vlm_path = vlm_extract_text_from_pdf(file_path)
    chunks = []
    chunks.extend(chunk_text("data/aides_notion/notes.txt"))
    embeddings.append(get_embeddings(chunks), axis=0)
    question = "Tu peux me donner et m'expliquer la définition de la Tower Property ?"
    answer_with_context(question, chunks, embeddings)
