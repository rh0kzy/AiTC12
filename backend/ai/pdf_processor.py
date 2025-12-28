import os
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

def convert_pdf_to_markdown(pdf_path: str) -> str:
    """
    Converts a PDF file to Markdown using Mistral OCR.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in .env file")

    client = Mistral(api_key=api_key)

    # Upload the file to Mistral with purpose="ocr"
    print(f"Uploading {pdf_path} to Mistral...")
    with open(pdf_path, "rb") as f:
        uploaded_file = client.files.upload(
            file={
                "file_name": os.path.basename(pdf_path),
                "content": f,
            },
            purpose="ocr"
        )

    # Get the signed URL for OCR
    file_url = client.files.get_signed_url(file_id=uploaded_file.id)

    # Process OCR
    print(f"Processing OCR for {pdf_path}...")
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": file_url.url,
        }
    )

    # Combine all pages into one markdown string
    full_markdown = ""
    for page in ocr_response.pages:
        full_markdown += page.markdown + "\n\n"

    # Clean up: delete the file from Mistral
    client.files.delete(file_id=uploaded_file.id)

    return full_markdown

if __name__ == "__main__":
    pass
