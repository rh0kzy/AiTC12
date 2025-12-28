from langdetect import detect_langs
text = "salut , je veux savoir vos plans"
try:
    predictions = detect_langs(text)
    print(predictions)
except Exception as e:
    print(e)
