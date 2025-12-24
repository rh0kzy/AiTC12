import re
from langdetect import detect_langs, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Ensure consistent results for language detection
DetectorFactory.seed = 0

class TicketPrechecker:
    def __init__(self):
        # Common spam keywords (English and French)
        self.spam_keywords = [
            "win money", "free gift", "click here", "subscribe now", 
            "lottery", "congratulations", "urgent action required",
            "buy now", "limited time", "cash prize", "earn money",
            "work from home", "no cost", "risk free", "winner",
            "claim now", "exclusive deal", "investment", "crypto", "bitcoin",
            "gagner de l'argent", "cadeau gratuit", "cliquez ici", "abonnez-vous",
            "loterie", "félicitations", "action urgente", "offre exclusive",
            "investissement", "gagner gros", "promotion", "rabais"
        ]

    def check_language(self, text):
        """Verify if the language is French or English with high confidence."""
        if len(text.strip()) < 10:
            # Too short to detect reliably, check for very specific keywords
            short_indicators = ["aide", "help", "svp", "please", "merci", "thanks", "bug"]
            return any(word in text.lower() for word in short_indicators)

        try:
            # Get all detected languages with their probabilities
            predictions = detect_langs(text)
            
            # We want 'fr' or 'en' to be the top prediction with a decent confidence
            # or at least present with high confidence
            for pred in predictions:
                if pred.lang in ['fr', 'en'] and pred.prob > 0.8:
                    return True
                
            # If top prediction is fr/en even with lower confidence, we check for specific indicators
            top_lang = predictions[0].lang
            if top_lang in ['fr', 'en'] and predictions[0].prob > 0.5:
                # Specific French/English words that are less likely to be in Spanish/Italian
                strong_indicators = [
                    "est", "sont", "fait", "marche", "probleme", "bonjour", "salut",
                    "the", "is", "are", "works", "problem", "hello", "thanks"
                ]
                if any(f" {word} " in f" {text.lower()} " for word in strong_indicators):
                    return True

            return False
        except LangDetectException:
            return False

    def is_spam(self, text):
        """Check for common spam keywords."""
        text_lower = text.lower()
        for keyword in self.spam_keywords:
            if keyword in text_lower:
                return True
        return False

    def run_precheck(self, ticket_content):
        """Run all prechecks and return a report."""
        results = {
            "is_supported_lang": self.check_language(ticket_content),
            "is_spam": self.is_spam(ticket_content),
            "passed": False,
            "reason": []
        }

        if not results["is_supported_lang"]:
            results["reason"].append("Language is not supported (Only French and English are accepted).")
        
        if results["is_spam"]:
            results["reason"].append("Ticket identified as spam.")

        # If it's a supported language and not spam, we let it pass
        if results["is_supported_lang"] and not results["is_spam"]:
            results["passed"] = True
            
        return results

if __name__ == "__main__":
    # Interactive mode
    checker = TicketPrechecker()
    print("--- Ticket Prechecker Interactive Mode ---")
    print("Type your ticket content below to test (or type 'exit' to quit):")
    
    while True:
        user_input = input("\nTicket > ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
        if not user_input.strip():
            continue
            
        results = checker.run_precheck(user_input)
        print("\nResults:")
        print(f"  Passed: {results['passed']}")
        print(f"  Supported Lang: {results['is_supported_lang']}")
        print(f"  Spam: {results['is_spam']}")
        if results['reason']:
            print(f"  Reasons: {', '.join(results['reason'])}")
        print("-" * 30)
