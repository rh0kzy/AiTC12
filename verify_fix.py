from ai.precheck import TicketPrechecker
from langdetect import detect_langs
checker = TicketPrechecker()
text = "salut , je veux savoir vos plans"
results = checker.run_precheck(text)
print(f"Text: {text}")
print(f"Predictions: {detect_langs(text)}")
print(f"Passed: {results['passed']}")
print(f"Reason: {results['reason']}")
