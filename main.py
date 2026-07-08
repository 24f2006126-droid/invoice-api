from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
from datetime import datetime

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


def parse_amount(value):
    if not value:
        return None

    value = value.replace(",", "")

    match = re.search(r"\d+(?:\.\d+)?", value)

    if match:
        return float(match.group())

    return None


def normalize_date(value):
    if not value:
        return None

    value = value.strip().replace(",", "")

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",

        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",

        "%d %B %Y",
        "%d %b %Y",

        "%B %d %Y",
        "%b %d %Y",

        "%d-%b-%Y",
        "%d-%B-%Y",

        "%b-%d-%Y",
        "%B-%d-%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")   # ISO format
        except ValueError:
            continue

    return None

def extract_date(text):
    patterns = [

        # Date labels
        r"(?:Date|Invoice Date|Issued|Issue Date)\s*[:\-]\s*([^\n]+)",

        # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
        r"\b(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b",

        # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
        r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b",

        # 22 May 2026
        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",

        # May 22 2026 or May 22, 2026
        r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",

        # 22-May-2026
        r"\b(\d{1,2}-[A-Za-z]{3,9}-\d{4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1).strip()
            date = normalize_date(value)

            if date:
                return date

    return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None
    }


    # Invoice number
    invoice_patterns = [
        r"Invoice\s*(?:No|Number)\s*[:#\-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*#\s*([A-Za-z0-9\-\/]+)",
        r"Ref\s*[:\-]\s*([A-Za-z0-9\-\/]+)"
    ]

    for pattern in invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            result["invoice_no"] = match.group(1).strip()
            break


    # Vendor
    vendor_patterns = [
        r"Vendor\s*[:\-]\s*(.+)",
        r"Supplier\s*[:\-]\s*(.+)",
        r"Company\s*[:\-]\s*(.+)"
    ]

    for pattern in vendor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            result["vendor"] = match.group(1).strip()
            break


    # Date
    result["date"] = extract_date(text)


    # Amount (subtotal before tax)
    amount_patterns = [
        r"Subtotal.*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})",
        r"Sub\s*Total.*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})"
    ]

    for pattern in amount_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            result["amount"] = parse_amount(match.group(1))
            break


    # Tax
    tax_patterns = [
        r"(?:GST|IGST|CGST|SGST|VAT|Tax).*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})"
    ]

    for pattern in tax_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            result["tax"] = parse_amount(match.group(1))
            break


    # Currency
    currency_match = re.search(
        r"Currency\s*[:\-]\s*([A-Za-z]+)",
        text,
        re.IGNORECASE
    )

    if currency_match:
        result["currency"] = currency_match.group(1).upper()

    elif re.search(r"\bRs\.?", text, re.IGNORECASE):
        result["currency"] = "INR"


    return result
