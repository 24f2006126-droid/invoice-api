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

    return float(match.group()) if match else None


def normalize_date(value):
    if not value:
        return None

    value = value.strip().replace(",", "")

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

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


    patterns = {

        "invoice_no": [
            r"Invoice\s*(?:No|Number)\s*[:#\-]?\s*([A-Za-z0-9\-\/]+)",
            r"Invoice\s*#\s*([A-Za-z0-9\-\/]+)",
            r"Ref\s*[:\-]\s*([A-Za-z0-9\-\/]+)"
        ],


        "vendor": [
            r"Vendor\s*[:\-]\s*(.+)",
            r"Supplier\s*[:\-]\s*(.+)",
            r"Company\s*[:\-]\s*(.+)",
            r"^(.+?)\s*(?:—|-)\s*Tax Invoice"
        ],


        "date": [
            r"(?:date|invoice\s*date|issued|issue\s*date|invoice\s*dt|date\s*of\s*issue|generated\s*date)\s*[:\-]?\s*(\d{4}[-/]\d{2}[-/]\d{2})",
            r"(?:date|invoice\s*date|issued|issue\s*date|invoice\s*dt|date\s*of\s*issue|generated\s*date)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
            r"(?:date|invoice\s*date|issued|issue\s*date|invoice\s*dt|date\s*of\s*issue|generated\s*date)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            r"(?:date|invoice\s*date|issued|issue\s*date|invoice\s*dt|date\s*of\s*issue|generated\s*date)\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2}\s+\d{4})"
        ],


        "amount": [
            r"Subtotal.*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})",
            r"Sub\s*Total.*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})"
        ],


        "tax": [
            r"(?:GST|IGST|CGST|SGST|VAT|Tax).*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})"
        ],


        "currency": [
            r"Currency\s*[:\-]\s*([A-Za-z]+)",
            r"\b(INR|USD|EUR|GBP)\b"
        ]
    }


    for key, regex_list in patterns.items():

        for pattern in regex_list:

            match = re.search(
                pattern,
                text,
                re.MULTILINE | re.IGNORECASE
            )

            if match:

                value = match.group(1).strip()

                if key in ["amount", "tax"]:
                    result[key] = parse_amount(value)

                elif key == "date":
                    result[key] = normalize_date(value)

                else:
                    result[key] = value

                break


    # Date fallback
    if result["date"] is None:
        match = re.search(
            r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b",
            text
        )

        if match:
            result["date"] = normalize_date(match.group(1))


    # Currency fallback
    if result["currency"] is None:

        if re.search(r"\bRs\.?", text, re.IGNORECASE):
            result["currency"] = "INR"


    return result