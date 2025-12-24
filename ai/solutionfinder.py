# solution_finder.py
import os
import json
import numpy as np
import chromadb
from chromadb.utils import embedding_functions
from mistralai import Mistral
from dotenv import load_dotenv, find_dotenv
try:
    from .pdf_processor import convert_pdf_to_markdown
except ImportError:
    from pdf_processor import convert_pdf_to_markdown
from langchain_experimental.text_splitter import SemanticChunker
from langchain_mistralai import MistralAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential
from circuitbreaker import circuit

# Load env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    raise ValueError("MISTRAL_API_KEY not found")

client = Mistral(api_key=API_KEY)

# LangChain embeddings for semantic chunking
lc_embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=API_KEY)

# -----------------------------
# ChromaDB Setup
# -----------------------------
# Initialize ChromaDB client (persistent storage)
# Path is now relative to this file (ai/chroma_db)
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "chroma_db")
chroma_client = chromadb.PersistentClient(path=db_path)

# Use ChromaDB's built-in Mistral embedding function
# It will automatically use the MISTRAL_API_KEY from the environment
mistral_ef = embedding_functions.MistralEmbeddingFunction(
    model="mistral-embed"
)

def get_or_create_collection(name="ticket_knowledge_base"):
    return chroma_client.get_or_create_collection(
        name=name, 
        embedding_function=mistral_ef
    )

# -----------------------------
# Ingestion
# -----------------------------
def ingest_pdf_to_chroma(pdf_path: str, category: str = "general", collection_name="ticket_knowledge_base"):
    """
    Converts PDF to Markdown via Mistral OCR and stores in ChromaDB.
    ChromaDB handles the embedding automatically.
    """
    collection = get_or_create_collection(collection_name)
    
    # 1. Convert PDF to Markdown
    markdown_content = convert_pdf_to_markdown(pdf_path)
    
    # 2. Semantic chunking using LangChain
    text_splitter = SemanticChunker(lc_embeddings, breakpoint_threshold_type="percentile")
    chunks = text_splitter.split_text(markdown_content)
    chunks = [c.strip() for c in chunks if c.strip()]
    
    # 3. Add to Chroma (Embeddings are handled by mistral_ef automatically)
    print(f"Ingesting {len(chunks)} chunks into ChromaDB (Category: {category})...")
    ids = [f"{os.path.basename(pdf_path)}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": pdf_path, "category": category} for _ in chunks]
    
    # Batching to avoid "Too many inputs" error from Mistral API
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        
        collection.add(
            documents=batch_chunks,
            ids=batch_ids,
            metadatas=batch_metadatas
        )
    print("Ingestion complete.")

# -----------------------------
# RAG Core
# -----------------------------
def retrieve_from_chroma(query, category: str = None, collection_name="ticket_knowledge_base", k=5):
    collection = get_or_create_collection(collection_name)
    
    # Prepare filter if category is provided
    where_filter = {"category": category} if category else None

    # ChromaDB handles the query embedding automatically
    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=where_filter
    )
    
    # Format results to match previous structure
    formatted_results = []
    if results['documents']:
        for i in range(len(results['documents'][0])):
            # ChromaDB returns distances (lower is better). 
            # We convert distance to a similarity score (0 to 1).
            # Common formula: 1 / (1 + distance)
            distance = results['distances'][0][i] if 'distances' in results and results['distances'] else 1.0
            similarity = 1.0 / (1.0 + distance)
            
            formatted_results.append((
                similarity,
                {
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "category": results['metadatas'][0][i].get("category") if results['metadatas'] else "N/A"
                }
            ))
    return formatted_results

def generate_answer(query, retrieved_docs):
    """
    Generate grounded answer using retrieved snippets
    """
    if not retrieved_docs:
        return "Désolé, je n'ai trouvé aucune information pertinente dans la base de connaissances pour répondre à votre demande."

    context = "\n\n".join(
        f"[Doc {i+1} - Catégorie: {doc.get('category', 'N/A')}] {doc['content'][:500]}"
        for i, (_, doc) in enumerate(retrieved_docs)
    )

    system_prompt = """You are a solution finder for Doxa.
Use ONLY the provided documents to answer.
If the information is not in the documents, say clearly that you don't have the information.
Answer in French.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"""
Context documents:
{context}

Question:
{query}

Answer with a clear solution and short explanation.
"""
        }
    ]

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=messages
    )

    return response.choices[0].message.content

def is_refusal(answer: str) -> bool:
    """
    Detects if the LLM answer is a refusal to answer due to lack of information.
    """
    refusal_keywords = [
        "ne contiennent pas", "pas d'informations", "pas d'information",
        "je ne sais pas", "information is missing", "not mentioned",
        "aucune information", "malheureusement", "don't have information",
        "do not contain", "no information", "not found",
        "not provide", "unable to find", "cannot find", "not available",
        "n'est pas mentionné", "ne précise pas", "ne mentionnent pas",
        "ne mentionne pas", "pas explicitement"
    ]
    answer_lower = answer.lower()
    return any(kw in answer_lower for kw in refusal_keywords)

# -----------------------------
# Main API
# -----------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@circuit(failure_threshold=3, recovery_timeout=60)
def solution_finder(query, category: str = None, collection_name="ticket_knowledge_base", top_k=5):
    """
    Finds a solution by searching in the specified category first.
    If no relevant documents are found OR if the answer is a refusal,
    it falls back to a global search across all categories.
    """
    # 1. Try with the specific category
    print(f"🔍 [RAG] Recherche dans la catégorie : {category or 'Toutes'}")
    retrieved = retrieve_from_chroma(query, category=category, collection_name=collection_name, k=top_k)
    
    # Similarity threshold
    SIMILARITY_THRESHOLD = 0.8
    best_score = retrieved[0][0] if retrieved else 0
    
    answer = generate_answer(query, retrieved)
    is_fallback = False

    # Check if we should fallback:
    # - Either the score is too low
    # - Or the LLM says it didn't find the info in the provided context
    if category and (best_score < SIMILARITY_THRESHOLD or is_refusal(answer)):
        reason = "score faible" if best_score < SIMILARITY_THRESHOLD else "information non trouvée dans cette catégorie"
        print(f"🔄 [RAG] Fallback ({reason}). Recherche élargie à toutes les catégories...")
        
        # 2. Fallback: Search in all categories
        retrieved_global = retrieve_from_chroma(query, category=None, collection_name=collection_name, k=top_k)
        
        # Only use global results if they are better or if we had a refusal
        best_global_score = retrieved_global[0][0] if retrieved_global else 0
        
        if best_global_score > best_score or is_refusal(answer):
            retrieved = retrieved_global
            answer = generate_answer(query, retrieved)
            is_fallback = True

    return {
        "query": query,
        "used_documents": [
            {"id": doc["id"], "content": doc["content"], "score": score, "category": doc.get("category")}
            for score, doc in retrieved
        ],
        "answer": answer,
        "fallback_used": is_fallback
    }


def test_similarity_on_kb_sample(sample_queries, collection_name="ticket_knowledge_base", threshold=0.8):
    """
    Tests similarity scores on sample KB entries.
    Queries the KB with sample queries and asserts that the best similarity score > threshold.
    """
    collection = get_or_create_collection(collection_name)
    
    # Check if collection has documents
    if collection.count() == 0:
        print("❌ KB is empty. Please ingest documents first.")
        return False
    
    all_passed = True
    for query in sample_queries:
        print(f"🔍 Testing query: '{query}'")
        retrieved = retrieve_from_chroma(query, collection_name=collection_name, k=1)
        
        if retrieved:
            best_score = retrieved[0][0]
            print(f"   Best similarity score: {best_score:.3f}")
            if best_score > threshold:
                print("   ✅ Passed (>0.8)")
            else:
                print("   ❌ Failed (<=0.8)")
                all_passed = False
        else:
            print("   ❌ No documents retrieved")
            all_passed = False
    
    return all_passed


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    # Example: Ingest a PDF if it exists
    # ingest_pdf_to_chroma("votre_document.pdf")

    # Test similarity on sample KB entries
    sample_queries = [
        "Comment réinitialiser mon mot de passe?",
        "Quels sont les délais de livraison?",
        "Quand est disponible le support technique?",
        "Puis-je retourner un article?"
    ]
    
    print("--- TESTING SIMILARITY >0.8 ON KB SAMPLE ---")
    test_passed = test_similarity_on_kb_sample(sample_queries, threshold=0.8)
    print(f"\nOverall test result: {'✅ PASSED' if test_passed else '❌ FAILED'}")
    
    user_query = input("\nEnter your question: ")
    result = solution_finder(user_query)

    print("\n--- RAG RESULT ---\n")
    print("Answer:\n", result["answer"])
    print("\nUsed documents:")
    for d in result["used_documents"]:
        print(f"- {d['id']}")
