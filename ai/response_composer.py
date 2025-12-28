# response_composer.py
import os
import json
from mistralai import Mistral
from dotenv import load_dotenv, find_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from circuitbreaker import circuit
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Ensure consistent results for language detection
DetectorFactory.seed = 0

# Load env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    raise ValueError("MISTRAL_API_KEY not found")

client = Mistral(api_key=API_KEY)

def detect_language(text: str) -> str:
    """
    Detect the language of the text. Returns 'fr' for French, 'en' for English, 'unknown' otherwise.
    """
    try:
        lang = detect(text)
        if lang in ['fr', 'en']:
            return lang
        return 'unknown'
    except LangDetectException:
        return 'unknown'

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@circuit(failure_threshold=3, recovery_timeout=60)
def compose_response(
    user_query: str,
    solution: str,
    evaluation: dict,
    escalation_context: dict | None = None
) -> dict:
    """
    Compose final structured response.
    """

    if evaluation.get("escalate"):
        return compose_escalation_response(user_query, evaluation)

    # Detect language
    detected_lang = detect_language(user_query)
    response_lang = "French" if detected_lang == 'fr' else "English"

    system_prompt = f"""You are a response composer for a technical support AI.

Generate a professional, clear and human response in {response_lang} with the following structure (use natural paragraphs, NO numbered lists):
- Polite acknowledgement / thanks
- Restatement of the user's problem
- Proposed solution
- Optional next steps or tips

IMPORTANT RULES:
- Use ONLY the information provided in the "Proposed solution" section
- Do NOT add, invent, or hallucinate any information not present in the proposed solution
- Ensure the response completely addresses the user's question using the provided solution
- If the solution is incomplete, do not attempt to complete it yourself
- Maintain a calm, professional, and reassuring tone
- Cover 100% of the user's question based on the available solution

Do NOT mention internal systems or evaluation scores.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"""
User query:
{user_query}

Proposed solution:
{solution}
"""
        }
    ]

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=messages
    )

    return {
        "final_response": response.choices[0].message.content,
        "escalated": False
    }


def compose_escalation_response(user_query: str, evaluation: dict) -> dict:
    """
    Safe response when escalation is required
    """

    # Detect language
    detected_lang = detect_language(user_query)
    response_lang = "French" if detected_lang == 'fr' else "English"

    system_prompt = f"""You are a support assistant.

Generate a calm response in {response_lang} that:
1. Acknowledges the issue
2. Explains that the request needs further review
3. Reassures the user that it is being escalated
4. Avoids technical details or blame

Tone:
- Empathetic
- Professional
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"""
User query:
{user_query}

Detected issues:
{evaluation["reason"]}
"""
        }
    ]

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=messages
    )

    return {
        "final_response": response.choices[0].message.content,
        "escalated": True
    }


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    query = "My system keeps crashing and I’m really frustrated"
    solution = "Try updating your dependencies and restarting the service."

    evaluation = {
        "confidence": 55,
        "negative_emotion": True,
        "sensitive_data": False,
        "non_standard": False,
        "escalate": True,
        "reason": "Low confidence and user frustration"
    }

    result = compose_response(query, solution, evaluation)

    print("\n--- Final Response ---\n")
    print(result["final_response"])
    print("\nEscalated:", result["escalated"])
