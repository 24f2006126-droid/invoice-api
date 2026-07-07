# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
from datetime import datetime

app = FastAPI()

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
    m = re.search(r"[\d.]+", value)
    return float(m.group()) if m else None


def normalize_date(value):
    if not value:
        return None

    value = value.strip().replace(",", "")

    formats = [
        "%d %B %Y",
        "%d %b %Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d %Y",
        "%b %d %Y"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except:
            pass

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
            r"Invoice\s*(?:No|Number)\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
            r"Ref\s*[:]\s*([A-Za-z0-9\-\/]+)"
        ],
        "vendor": [
            r"Vendor\s*[:]\s*(.+)",
            r"^(.+?)\s*(?:—|-)\s*Tax Invoice"
        ],
        "date": [
    r"(?:Date|Invoice Date|Issued|Issue Date)\s*[:\-]?\s*(\d{4}[-/]\d{2}[-/]\d{2})",
    r"(?:Date|Invoice Date|Issued|Issue Date)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
    r"(?:Date|Invoice Date|Issued|Issue Date)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    r"(?:Date|Invoice Date|Issued|Issue Date)\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
],
        "amount": [
            r"Subtotal.*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})",
        ],
        "tax": [
            r"(?:GST|IGST|CGST|SGST|Tax).*?(?:Rs\.?|INR|\$)?\s*([\d,]+\.\d{2})"
        ],
        "currency": [
            r"Currency\s*[:]\s*([A-Za-z]+)"
        ]
    }

    for key, pats in patterns.items():
        for p in pats:
            m = re.search(p, text, re.MULTILINE | re.IGNORECASE)
            if m:
                value = m.group(1).strip()

                if key in ["amount", "tax"]:
                    result[key] = parse_amount(value)
                elif key == "date":
                    result[key] = normalize_date(value)
                else:
                    result[key] = value

                break

    # Infer INR when Rs. appears
    if result["currency"] is None and re.search(r"\bRs\.?", text, re.I):
        result["currency"] = "INR"

    return result