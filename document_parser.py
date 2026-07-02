import io
import pandas as pd
import fitz
import easyocr
import numpy as np
import logging
logging.basicConfig(filename='audit.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Initializing EasyOCR Model...")
reader = easyocr.Reader(['en'], gpu=False)
def extract_text(file_name: str, file_bytes: bytes) -> str:
    """Routes the uploaded file bytes to the correct extraction method."""
    text = ""
    try:
        if file_name.lower().endswith('.pdf'):
            text = extract_from_pdf(file_bytes)
        elif file_name.lower().endswith('.csv'):
            text = extract_from_csv(file_bytes)
        elif file_name.lower().endswith('.txt'):
            text = extract_from_txt(file_bytes)
        else:
            logging.warning(f"Unsupported file type attempted: {file_name}")
            return "Unsupported file format. Please upload PDF, TXT, or CSV."
        logging.info(f"Successfully extracted text from {file_name}")
        return text
    except Exception as e:
        logging.error(f"Error extracting text from {file_name}: {str(e)}")
        return f"Error reading file: {str(e)}"
def extract_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode('utf-8', errors='ignore')
def extract_from_csv(file_bytes: bytes) -> str:
    df = pd.read_csv(io.BytesIO(file_bytes))
    return df.to_string()
def extract_from_pdf(file_bytes: bytes) -> str:
    extracted_text = ""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if not text or len(text.strip()) < 10:
            logging.info(f"Triggering EasyOCR on page {page_num + 1}")
            try:
                pix = page.get_pixmap()
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                results = reader.readtext(img_array, detail=0)
                text = " ".join(results)
            except Exception as e:
                logging.error(f"OCR failed on page {page_num+1}: {str(e)}")
                text = f"\n[OCR Failed on page {page_num+1}]\n"
        extracted_text += (text if text else "") + "\n\n"
    return extracted_text
