import os
import json
import re
from dotenv import load_dotenv
from mistralai import Mistral

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
API_KEY = os.getenv("MISTRAL_API_KEY")


class DeterministicEvaluator:
    """
    Evaluator & Decider for support RAG systems:
    - Computes confidence_score
    - Detects exceptions (negative emotions, sensitive data, non-standard)
    - Escalates if needed
    """

    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        r"\b(?:\d[ -]*?){12,18}\d\b",  # credit card numbers (13-19 digits with spaces/dashes)
        r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b",  # emails
        r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?(?:[-.\s]?\d{2,4}){3,5}\b"  # phone numbers
    ]

    def __init__(self, confidence_threshold: float = 0.6):
        if not API_KEY:
            raise ValueError("MISTRAL_API_KEY not found in .env file")

        self.client = Mistral(api_key=API_KEY)
        self.model = "mistral-small-latest"
        self.threshold = confidence_threshold

    def _detect_sensitive_data(self, text: str) -> bool:
        for i, p in enumerate(self.SENSITIVE_PATTERNS):
            matches = re.finditer(p, text)
            for m in matches:
                match_text = m.group()
                # For phone numbers (index 2), ensure at least 10 digits in the match itself
                if i == 2:
                    digit_count = sum(c.isdigit() for c in match_text)
                    if digit_count >= 10:
                        # Check if it's not just a sequence of steps like "1. ... 2. ... 10."
                        # A real phone number usually doesn't have words in between digits
                        # but our regex already handles some separators.
                        return True
                else:
                    return True
        return False

    def evaluate(self, query: str, context: str, response: str, retrieval_score: float = 0.5) -> dict:
        """
        Returns minimal evaluation object with confidence and escalation context.
        """

        # Auto escalate if context too weak
        if not context or len(context.strip()) < 20:
            return self._escalation_payload(
                confidence=0.0,
                sentiment="neutral",
                sensitive_data=False,
                non_standard=True,
                is_refusal=False,
                reason="No reliable context",
                query=query,
                response=response
            )

        system_prompt = """
You are an expert evaluator for a support RAG system.

Your task:
1. Assign a GLOBAL CONFIDENCE SCORE (0.0 to 1.0) for the AI response based on the context.
3. Detect the sentiment of the USER QUERY:
   - "positive": happy, thankful, satisfied.
   - "neutral": objective, just asking a question.
   - "frustrated": annoyed, impatient, but still polite.
   - "angry": upset, using strong language, or very demanding.
4. Detect:
   - Sensitive data (credit cards, private emails, private phone numbers). 
     NOTE: Do NOT flag public support emails (e.g., support@doxa.fr), support phone numbers, company contact info, login attempts, or general frustration as sensitive data.
   - Non-standard or ambiguous requests
   - Refusal: true if the AI response says it doesn't know or cannot answer.
5. Escalate if:
   - Confidence < 0.6
   - Sensitive data (PII) detected in the AI response.
   - Sentiment is "angry".

Respond ONLY in valid JSON:
{
  "confidence": 0.0-1.0,
  "sentiment": "positive" | "neutral" | "frustrated" | "angry",
  "sensitive_data": true/false,
  "non_standard": true/false,
  "is_refusal": true/false,
  "reason": "short explanation"
}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""
USER QUERY:
{query}

CONTEXT:
{context}

AI RESPONSE:
{response}
"""
            }
        ]

        try:
            completion = self.client.chat.complete(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )

            raw = completion.choices[0].message.content
            result = json.loads(raw)

            # Confidence + soft retrieval bonus
            confidence = round((0.8 * float(result.get("confidence", 0.0)) + 0.2 * retrieval_score), 2)

            # Detect sensitive data (Regex on query/response + LLM check)
            regex_sensitive = self._detect_sensitive_data(query) or self._detect_sensitive_data(response)
            llm_sensitive = result.get("sensitive_data", False)
            
            # Trust LLM more for emails/phones (often support info), but keep Regex for credit cards
            sensitive_data_detected = llm_sensitive
            reason = result.get("reason", "")

            if regex_sensitive and not llm_sensitive:
                # Check if it's a credit card (Pattern 0)
                if any(re.search(self.SENSITIVE_PATTERNS[0], t) for t in [query, response]):
                    sensitive_data_detected = True
                    reason = f"Credit card pattern detected (Regex). {reason}".strip()
                else:
                    # If it's just email/phone and LLM says it's fine, we trust the LLM (likely support info)
                    # But we still log it in the reason for transparency
                    reason = f"Note: Potential contact info detected by Regex but cleared by LLM. {reason}".strip()

            # Decide escalation
            sentiment = result.get("sentiment", "neutral")
            escalate = confidence < self.threshold or sensitive_data_detected or sentiment == "angry"

            if escalate:
                return self._escalation_payload(
                    confidence=confidence,
                    sentiment=sentiment,
                    sensitive_data=sensitive_data_detected,
                    non_standard=result.get("non_standard", False),
                    is_refusal=result.get("is_refusal", False),
                    reason=reason,
                    query=query,
                    response=response
                )

            return {
                "confidence_score": confidence,
                "escalate": False,
                "sentiment": sentiment,
                "sensitive_data": sensitive_data_detected,
                "non_standard": result.get("non_standard", False),
                "is_refusal": result.get("is_refusal", False),
                "reason": reason
            }

        except Exception as e:
            return self._escalation_payload(
                confidence=0.0,
                sentiment="neutral",
                sensitive_data=False,
                non_standard=True,
                is_refusal=False,
                reason=f"Evaluation failure: {str(e)}",
                query=query,
                response=response
            )

    def _escalation_payload(
        self,
        confidence: float,
        sentiment: str,
        sensitive_data: bool,
        non_standard: bool,
        is_refusal: bool,
        reason: str,
        query: str,
        response: str
    ) -> dict:
        """
        Structured escalation payload for human agent.
        """
        return {
            "confidence_score": confidence,
            "escalate": True,
            "sentiment": sentiment,
            "sensitive_data": sensitive_data,
            "non_standard": non_standard,
            "is_refusal": is_refusal,
            "reason": reason,
            "escalation_context": {
                "user_query": query,
                "ai_response": response
            }
        }


# -----------------------
# Quick usage test
# -----------------------
if __name__ == "__main__":
    evaluator = DeterministicEvaluator()

    # Test 1: Sensitive data (Email)
    ctx1 = "The company offers a 30-day refund policy on all electronics."
    qry1 = "I'm very angry, can I get my money back?"
    ans1 = "Yes, you can request a refund within 30 days of purchase. My email is test@example.com."

    print("--- Test 1: Email (Should be sensitive) ---")
    result1 = evaluator.evaluate(query=qry1, context=ctx1, response=ans1, retrieval_score=0.9)
    print(json.dumps(result1, indent=2, ensure_ascii=False))

    # Test 2: Date (Should NOT be sensitive)
    ctx2 = "Today is 2025-12-23. We are open until 18:00."
    qry2 = "What is the date today?"
    ans2 = "Today is 2025-12-23 and we are here to help."

    print("\n--- Test 2: Date (Should NOT be sensitive) ---")
    result2 = evaluator.evaluate(query=qry2, context=ctx2, response=ans2, retrieval_score=0.9)
    print(json.dumps(result2, indent=2, ensure_ascii=False))

    # Test 3: User's problematic query
    ctx3 = "Pour vous connecter, utilisez votre identifiant Doxa."
    qry3 = "C'est la troisième fois que j'essaie de me connecter et ça ne marche toujours pas ! Je commence vraiment à perdre patience avec votre outil, c'est inadmissible."
    ans3 = "Je suis désolé pour ce désagrément. Pour résoudre votre problème de connexion, veuillez vérifier vos identifiants."

    print("\n--- Test 3: Frustrated user (Should NOT be sensitive) ---")
    result3 = evaluator.evaluate(query=qry3, context=ctx3, response=ans3, retrieval_score=0.9)
    print(json.dumps(result3, indent=2, ensure_ascii=False))

    # Test 4: Many steps (Should NOT be sensitive)
    ctx4 = "Follow these steps to reset your password."
    qry4 = "How to reset password?"
    ans4 = "1. Go to settings. 2. Click security. 3. Select password. 4. Enter old. 5. Enter new. 6. Confirm. 7. Save. 8. Logout. 9. Login. 10. Done."

    print("\n--- Test 4: Many steps (Should NOT be sensitive) ---")
    result4 = evaluator.evaluate(query=qry4, context=ctx4, response=ans4, retrieval_score=0.9)
    print(json.dumps(result4, indent=2, ensure_ascii=False))
