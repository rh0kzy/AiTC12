# queryanalyser.py
import os
import json
from mistralai import Mistral
from dotenv import load_dotenv, find_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from circuitbreaker import circuit

# Load environment variables from .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
API_KEY = os.environ.get("MISTRAL_API_KEY")
if not API_KEY:
    raise ValueError("Please set MISTRAL_API_KEY in your .env file")

# Initialize Mistral client
client = Mistral(api_key=API_KEY)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@circuit(failure_threshold=3, recovery_timeout=60)
def analyse_query(query: str) -> dict:
    """
    Sends a query to Mistral and returns a summary, keywords, and an optimized version.
    Output format:
    {
        "summary": "short summary of the query",
        "keywords": ["key", "words", "here"],
        "category": "category_name",
        "is_sufficient": true/false,
        "is_in_scope": true/false,
        "optimized_query": "expanded query with synonyms and details"
    }
    """
    # Prompt for the model
    system_prompt = """You are an expert query analyzer for a technical support system (Company: Doxa).
Your task is to:
1. Provide a short summary of less than 100 words of the query in French.
2. Evaluate if the query is sufficient (detailed enough) to find a precise solution.
3. Evaluate if the query is 'is_in_scope':
   - True if it's related to Doxa, technical support, user guides, or professional services.
   - False if it's completely unrelated (e.g., cooking, sports, general jokes, other companies).
4. Provide an 'optimized_query':
   - If the query is too short or vague, expand it by detailing the likely technical context.
   - Replace common words with technical synonyms to improve search results (RAG).
5. Extract from 5 to 10 key keywords (recommended 7).
6. Identify the 'category' of the query among: 
   - 'Legal, Regulatory, and Commercial Frameworks'
   - 'Support and Reference Documentation'
   - 'Operational and Practical User Guides'
   - 'Other' (if it doesn't fit the above)
7. Identify the 'agent_role' to route the query to:
   - 'agt_tech': if the query is technical, related to bugs, errors, setup, or user guides.
   - 'agt_sales': if the query is commercial, related to pricing, contracts, or legal frameworks.
8. Evaluate if the query is sufficient (detailed enough) to find a precise solution.
9. Evaluate if the query is 'is_in_scope':
   - True if it's related to Doxa, technical support, user guides, or professional services.
   - False if it's completely unrelated (e.g., cooking, sports, general jokes, other companies).
10. Provide an 'optimized_query':
   - If the query is too short or vague, expand it by detailing the likely technical context.
   - Replace common words with technical synonyms to improve search results (RAG).


Respond ONLY in JSON format:
{
    "summary": "...",
    "keywords": ["...", "..."],
    "category": "...",
    "agent_role": "agt_tech" | "agt_sales",
    "is_sufficient": true,
    "is_in_scope": true,
    "optimized_query": "..."
}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]

    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=messages,
            response_format={"type": "json_object"}  # Force JSON output
        )
        # Extract JSON from model
        content = response.choices[0].message.content
        result = json.loads(content)
    except Exception as e:
        print(f"Erreur lors de l'appel à l'API Mistral : {e}")
        result = {
            "summary": "[Erreur de connexion ou de traitement]", 
            "keywords": [],
            "is_sufficient": False,
            "optimized_query": query,
            "error": str(e)
        }

    return result

if __name__ == "__main__":
    query = input("Enter your query or text: ")
    result = analyse_query(query)

    print("\n--- Query Analysis ---\n")
    print(f"Summary:\n{result.get('summary')}\n")
    print(f"Category:\n{result.get('category')}\n")
    print(f"Keywords:\n{', '.join(result.get('keywords', []))}")
