import re
import time
from typing import Optional
from rapidfuzz import fuzz
from router.logger import logger

# ==============================================================================
# DOCUMENT RULES
# ==============================================================================
DOCUMENT_CHECK_ORDER = ["gst", "aadhar", "pan", "udyam", "bank_statement", "itr"]

DOCUMENT_KEYWORDS = {
    "gst": ["gst", "gstin", "registration certificate", "form gst reg 06"],
    "aadhar": ["government of india", "uidai", "date of birth", "male", "female"],
    "pan": ["permanent account number", "income tax department", "pan", "father"],
    "udyam": ["udyam", "udyam registration", "enterprise name"],
    "itr": [
        "indian income tax return acknowledgement",
        "acknowledgement number",
        "assessment year",
        "income tax return"
    ],
    "bank_statement": [
        "statement of account",
        "account no",
        "statement dt",
        "city union bank",
        "customer no"
    ]
}

PATTERNS = {
    "itr": {
        "acknowledgement_number": r"acknowledgement\s*number\s*[:\-]?\s*(\d{15})",
        "date_of_filing": r"date\s*of\s*filing\s*[:\-]?\s*(\d{1,2}-[A-Za-z]{3}-\d{4})"
    },
    "aadhar": {
        "number": r"\b\d{4}\s?\d{4}\s?\d{4}\b"
    },
    "pan": {
        "number": r"\b[A-Z]{5}\d{4}[A-Z]\b"
    },
    "udyam": {
        "number": r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b"
    },
    "gst": {
        "number": r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b"
    },
    "bank_statement": {
        "account_no": r"account\s*no\s*[:\-]?\s*(\d{9,18})",
        "customer_number": r"customer\s*no\s*[:\-]?\s*(\d+)",
        "ckyc_no": r"ckyc\s*no\s*[:\-]?\s*(\d+)"
    }
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_document_by_regex(text: str, run_id: int) -> Optional[str]:
    start = time.perf_counter()
    logger.info(f"[RUN {run_id}] Starting regex-based document detection")
    scores = {}

    for doc, fields in PATTERNS.items():
        match_count = sum(
            1 for rx in fields.values()
            if re.search(rx, text, re.IGNORECASE)
        )
        scores[doc] = match_count

    best_doc = max(scores, key=scores.get)
    latency = time.perf_counter() - start
    logger.info(f"[RUN {run_id}] Regex detection completed in {latency:.4f}s")
    return best_doc if scores[best_doc] > 0 else None


def detect_document_type_fuzzy(text: str, run_id: int, threshold=70):
    start = time.perf_counter()
    logger.info(
        f"[RUN {run_id}] Starting fuzzy document type detection with threshold={threshold}"
    )

    regex_doc = detect_document_by_regex(text, run_id)
    if regex_doc:
        return regex_doc, {regex_doc: 100}

    text_norm = normalize_text(text)
    scores = {}

    for doc in DOCUMENT_CHECK_ORDER:
        hits = []
        for kw in DOCUMENT_KEYWORDS[doc]:
            kw_norm = normalize_text(kw)
            if kw_norm in text_norm:
                hits.append(100)
            else:
                s = fuzz.partial_ratio(kw_norm, text_norm)
                if s >= threshold:
                    hits.append(s)

        if hits:
            avg = sum(hits) / len(hits)
            ratio = len(hits) / len(DOCUMENT_KEYWORDS[doc])
            scores[doc] = avg * 0.7 + ratio * 100 * 0.3
        else:
            scores[doc] = 0

    best = max(scores, key=scores.get)
    latency = time.perf_counter() - start
    logger.info(
        f"[RUN {run_id}] Fuzzy detection completed in {latency:.4f}s"
        f" - Result: {best}, Scores: {scores}"
    )
    return (best if scores[best] >= 65 else "unknown"), scores