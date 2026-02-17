import re
import time
from typing import Dict, Optional
from router.logger import logger
from router.document_classifier import PATTERNS


def extract_assessment_year(text: str) -> Optional[str]:
    years = re.findall(r"20\d{2}\s*-\s*\d{2,4}", text)
    if not years:
        return None

    fy_match = re.search(
        r"financial\s*year\s*(20\d{2}\s*-\s*\d{2,4})",
        text,
        re.IGNORECASE
    )
    if fy_match:
        years = [y for y in years if y != fy_match.group(1)]

    return years[0] if years else None


def extract_statement_date(text: str) -> Optional[str]:
    match = re.search(
        r"statement\s*dt\s*[:\-]?\s*([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}\s*to\s*[0-9]{1,2}-[A-Za-z]{3}-[0-9]{4})",
        text,
        re.IGNORECASE
    )
    return match.group(1) if match else None


def extract_document_fields(doc_type: str, text: str, run_id: int) -> Dict[str, str]:
    start = time.perf_counter()
    logger.info(f"[RUN {run_id}] Starting field extraction for document type: {doc_type}")
    out = {}

    for k, rx in PATTERNS.get(doc_type, {}).items():
        m = re.search(rx, text, re.IGNORECASE)
        if m:
            out[k] = (m.group(1) if m.lastindex else m.group()).strip().rstrip(".")

    if doc_type == "itr":
        ay = extract_assessment_year(text)
        if ay:
            out["assessment_year"] = ay

    if doc_type == "bank_statement":
        out.setdefault("account_no", None)
        out.setdefault("customer_number", None)
        out.setdefault("ckyc_no", None)
        out["statement_date"] = extract_statement_date(text)

    latency = time.perf_counter() - start
    logger.info(
        f"[RUN {run_id}] Field extraction completed in {latency:.4f}s"
        f" - Extracted fields: {list(out.keys())}"
    )
    return out