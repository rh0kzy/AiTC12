import os
from solutionfinder import ingest_pdf_to_chroma

# Chemin vers le fichier PDF
PDF_PATH = r"C:\Users\PC\Desktop\Studies\TC_PROJECT\ai\docs\Support\Guide_Utilisateur_Doxa.pdf"
CATEGORY = "Operational and Practical User Guides"

def run_specific_ingestion():
    print(f"--- Démarrage de l'ingestion pour : {os.path.basename(PDF_PATH)} ---")
    
    if not os.path.exists(PDF_PATH):
        print(f"Erreur : Le fichier {PDF_PATH} est introuvable.")
        return

    try:
        # On utilise la fonction modifiée dans solutionfinder.py qui gère déjà les lots de 50
        ingest_pdf_to_chroma(PDF_PATH, category=CATEGORY)
        print("\n✅ Ingestion réussie avec succès par lots de 50 !")
    except Exception as e:
        print(f"\n❌ Erreur lors de l'ingestion : {e}")

if __name__ == "__main__":
    run_specific_ingestion()
