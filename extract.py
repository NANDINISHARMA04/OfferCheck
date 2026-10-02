"""Turn an uploaded offer letter (PDF / image / txt) into plain text.

PDF: uses pypdf (pip install pypdf).
Image (WhatsApp screenshot): uses Tesseract OCR (pytesseract + the
tesseract program installed on your system). If OCR isn't installed,
we return a clear error instead of crashing.
"""
import io


class ExtractionError(Exception):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        return _pdf(data)
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return _image(data)
    raise ExtractionError("Upload a PDF, image (PNG/JPG) or .txt file.")


def _pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ExtractionError("PDF support needs pypdf: pip install pypdf") from e
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:10])
    if not text.strip():
        raise ExtractionError("This PDF has no selectable text (it may be a scanned image). "
                              "Take a screenshot and upload it as an image instead.")
    return text


def _image(data: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise ExtractionError("Image support needs OCR: pip install pytesseract pillow, "
                              "and install Tesseract on your computer.") from e
    try:
        text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
    except pytesseract.TesseractNotFoundError as e:
        raise ExtractionError("Tesseract is not installed on this computer. See README.") from e
    if not text.strip():
        raise ExtractionError("No readable text found in the image. Try a clearer screenshot.")
    return text
