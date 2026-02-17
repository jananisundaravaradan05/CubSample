import time
from router.logger import logger
from router.ocr_extractor import extract_text_from_document
from router.document_classifier import detect_document_type_fuzzy
from router.name_matcher import match_name
from router.field_extractor import extract_document_fields


def format_latency(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} sec"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} hr"


def measure_full_latency(start_time: float, result: dict) -> dict:
    total_latency = time.perf_counter() - start_time
    result.setdefault("ocr", {})["latency"] = format_latency(total_latency)
    return result


def process_document(file_path: str, file_name: str, user_document_type: str, user_name: str, run_id: int) -> dict:
    start = time.perf_counter()
    logger.info(f"[RUN {run_id}] Starting document processing")

    user_document_type = user_document_type.strip().lower()

    ocr_text, _ = extract_text_from_document(file_path, run_id)

    detected, _ = detect_document_type_fuzzy(ocr_text, run_id)
    detected = detected.lower() if detected else "unknown"

    name_ok, name_score = match_name(user_name, ocr_text, run_id)

    fields = extract_document_fields(detected, ocr_text, run_id) if detected == user_document_type else {}

    document_verified = detected == user_document_type
    status_value = "success" if document_verified and name_ok else "failed"

    latency = time.perf_counter() - start
    logger.info(f"[RUN {run_id}] Document processing completed in {latency:.3f}s - Status: {status_value}")
    logger.info(f"[RUN {run_id}] Detected: {detected} | Expected: {user_document_type} | Name score: {name_score}")

    return {
        "input": {
            "file_name": file_name,
            "document_type": user_document_type,
            "user_name": user_name
        },
        "status": status_value,
        "verification": {
            "document_type_detected": detected,
            "document_verified": document_verified,
            "name_verified": name_ok,
            "name_match_score": round(name_score, 2)
        },
        "ocr": {
            "text_preview": ocr_text
        },
        "extracted_fields": fields
    }