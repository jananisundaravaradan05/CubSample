import time
from rapidfuzz import fuzz
from router.logger import logger
from router.document_classifier import normalize_text


def match_name(user_name: str, ocr_text: str, run_id: int):
    start = time.perf_counter()
    logger.info(f"[RUN {run_id}] Starting name matching for: {user_name}")

    score = fuzz.partial_ratio(normalize_text(user_name), normalize_text(ocr_text))
    matched = score >= 90

    latency = time.perf_counter() - start
    logger.info(
        f"[RUN {run_id}] Name matching completed in {latency:.4f}s"
        f" - Score: {score}, Matched: {matched}"
    )
    return matched, score