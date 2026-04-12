"""
AI Line Item Extractor — Uses Azure OpenAI GPT-4o to extract line items from documents.

Supports: PDF, images (PNG/JPG/TIFF), Excel, CSV, Word (.docx)
"""

import base64
import csv
import io
import json
import logging
import os

logger = logging.getLogger(__name__)

# GPT-4o pricing (USD)
COST_PER_1M_INPUT_TOKENS = 2.50
COST_PER_1M_OUTPUT_TOKENS = 10.00

MAX_ITEMS = 100

SYSTEM_PROMPT = """You are a document analysis assistant. Extract all purchasable line items from the provided document.

For each item, return:
- description: Brief item description
- quantity: Number of units (integer, default 1 if not specified)
- unit_price: Price per unit in USD (numeric, no currency symbols)

Return a JSON object with a single key "items" containing an array.
Example: {"items": [{"description": "Widget A", "quantity": 10, "unit_price": 25.50}]}

If no line items are found, return: {"items": []}
Do not invent items — only extract what is explicitly in the document."""

# Image MIME types that GPT-4o vision can handle
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/gif", "image/webp", "image/bmp"}


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost in USD from token counts."""
    input_cost = (prompt_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost = (completion_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    return round(input_cost + output_cost, 6)


def check_budget():
    """Check if AI spending is within budget.

    Returns:
        tuple: (within_budget, total_spent, budget_limit)
    """
    from models import AIUsageLog, db

    total_spent = db.session.query(
        db.func.coalesce(db.func.sum(AIUsageLog.estimated_cost_usd), 0)
    ).scalar()
    budget_limit = float(os.environ.get("AZURE_OPENAI_BUDGET_LIMIT", "100.00"))
    return (float(total_spent) < budget_limit, float(total_spent), budget_limit)


def _get_client():
    """Create Azure OpenAI client."""
    from openai import AzureOpenAI

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    key = os.environ.get("AZURE_OPENAI_KEY", "")

    if not endpoint or not key:
        raise ValueError("Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY.")

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=key,
        api_version="2024-12-01-preview",
    )


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF. Returns empty string if scanned/image-based."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning("PDF text extraction failed: %s", e)
        return ""


def _extract_text_from_docx(file_path: str) -> str:
    """Extract text from Word document."""
    try:
        from docx import Document

        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.warning("DOCX text extraction failed: %s", e)
        return ""


def _extract_text_from_excel(file_path: str) -> str:
    """Extract text from Excel file as CSV-like text."""
    try:
        from openpyxl import load_workbook

        wb = load_workbook(file_path, read_only=True, data_only=True)
        text_parts = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(cells):
                    text_parts.append(" | ".join(cells))
        wb.close()
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning("Excel text extraction failed: %s", e)
        return ""


def _extract_text_from_csv(file_path: str) -> str:
    """Extract text from CSV file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = []
            for i, row in enumerate(reader):
                if i >= 500:  # Cap at 500 rows
                    break
                rows.append(" | ".join(row))
        return "\n".join(rows)
    except Exception as e:
        logger.warning("CSV text extraction failed: %s", e)
        return ""


def _file_to_base64(file_path: str) -> str:
    """Read file and return base64-encoded string."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _validate_items(raw_items: list) -> list:
    """Validate and sanitize extracted items."""
    validated = []
    for item in raw_items[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("description", "")).strip()
        if not desc:
            continue
        try:
            qty = max(1, int(float(item.get("quantity", 1))))
        except (ValueError, TypeError):
            qty = 1
        try:
            price = max(0.0, round(float(item.get("unit_price", 0)), 2))
        except (ValueError, TypeError):
            price = 0.0
        validated.append({
            "description": desc[:500],  # Cap description length
            "quantity": qty,
            "unit_price": price,
        })
    return validated


def extract_line_items(file_path: str, mime_type: str) -> dict:
    """Extract line items from a document using Azure OpenAI GPT-4o.

    Args:
        file_path: Path to the uploaded file
        mime_type: MIME type of the file

    Returns:
        dict with keys:
            items: list of {"description": str, "quantity": int, "unit_price": float}
            prompt_tokens: int
            completion_tokens: int
            total_tokens: int
            warning: str or None
    """
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    result = {"items": [], "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "warning": None}

    try:
        client = _get_client()
    except ValueError as e:
        result["warning"] = str(e)
        return result

    use_vision = False
    document_text = ""

    # Determine extraction strategy based on MIME type
    mime_lower = (mime_type or "").lower()

    if mime_lower in IMAGE_TYPES:
        use_vision = True
    elif mime_lower == "application/pdf":
        document_text = _extract_text_from_pdf(file_path)
        # If PDF has minimal text, treat as scanned image
        if len(document_text.strip()) < 50:
            use_vision = True
    elif mime_lower in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        document_text = _extract_text_from_docx(file_path)
    elif mime_lower in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ):
        document_text = _extract_text_from_excel(file_path)
    elif mime_lower == "text/csv":
        document_text = _extract_text_from_csv(file_path)
    elif mime_lower in ("text/plain", "text/markdown"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            document_text = f.read(100_000)  # Cap at 100KB
    else:
        # Try text extraction as fallback
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                document_text = f.read(100_000)
        except Exception:
            result["warning"] = f"Unsupported file type: {mime_type}"
            return result

    if not use_vision and not document_text.strip():
        result["warning"] = "No text content could be extracted from this document."
        return result

    # Build messages for GPT-4o
    try:
        if use_vision:
            b64_data = _file_to_base64(file_path)
            img_mime = mime_lower if mime_lower in IMAGE_TYPES else "image/png"
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract all line items from this document image."},
                    {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{b64_data}"}},
                ]},
            ]
        else:
            # Truncate text to ~80K chars to stay within token limits
            if len(document_text) > 80_000:
                document_text = document_text[:80_000] + "\n\n[... document truncated ...]"
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract line items from this document:\n\n{document_text}"},
            ]

        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout=60,
        )

        result["prompt_tokens"] = response.usage.prompt_tokens
        result["completion_tokens"] = response.usage.completion_tokens
        result["total_tokens"] = response.usage.total_tokens

        # Log token usage
        cost = calculate_cost(response.usage.prompt_tokens, response.usage.completion_tokens)
        logger.info(
            "AI extraction: %d prompt + %d completion = %d total tokens, est. cost $%.4f",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            cost,
        )

        # Parse response
        content = response.choices[0].message.content
        parsed = json.loads(content)

        raw_items = parsed.get("items", [])
        if isinstance(raw_items, list):
            result["items"] = _validate_items(raw_items)
        else:
            result["warning"] = "AI returned unexpected format."

    except json.JSONDecodeError:
        logger.warning("Failed to parse AI response as JSON")
        result["warning"] = "AI returned invalid response format."
    except Exception as e:
        error_type = type(e).__name__
        logger.error("AI extraction failed (%s): %s", error_type, e)
        if "timeout" in error_type.lower() or "Timeout" in str(e):
            result["warning"] = "AI processing timed out. Try a smaller document."
        elif "RateLimit" in error_type:
            result["warning"] = "AI service rate limit reached. Please try again in a moment."
        else:
            result["warning"] = "AI extraction encountered an error. Please try again."

    return result
