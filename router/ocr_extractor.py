import time
from typing import Tuple
from paddleocr import PaddleOCR
from router.logger import logger

ocr = PaddleOCR(
    lang="en",
    det=True,
    rec=True,
    cls=True,
    use_angle_cls=True,
    enable_mkldnn=True,
    show_log=False,
    use_gpu=False
)


def extract_text_from_document(file_path: str, run_id: int) -> Tuple[str, float]:
    start = time.perf_counter()
    logger.info(f"[RUN {run_id}] Starting OCR text extraction from: {file_path}")
    all_text = []

    result = ocr.ocr(file_path, cls=True)
    if result and result[0]:
        for line in result[0]:
            all_text.append(line[1][0])

    text = " ".join(all_text)
    latency = time.perf_counter() - start
    logger.info(
        f"[RUN {run_id}] OCR extraction completed in {latency:.3f}s"
        f" - Extracted {len(text)} characters"
    )
    return text, latency