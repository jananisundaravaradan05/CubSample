import time
import torch
from transformers import OwlViTProcessor, OwlViTForObjectDetection
from router.logger import logger

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
THRESHOLD = 0.02

TEXT_QUERIES = [[
    "document",
    "paper document",
    "identity card",
    "plastic card",
    "card",
    "form"
]]

processor = OwlViTProcessor.from_pretrained("google/owlvit-base-patch32")
model = OwlViTForObjectDetection.from_pretrained(
    "google/owlvit-base-patch32"
).to(DEVICE).eval()


def detect_best_box(image_rgb, run_id: int):
    start = time.perf_counter()
    H, W = image_rgb.shape[:2]
    logger.info(f"[RUN {run_id}] Starting OWL-ViT object detection on image ({W}x{H})")

    inputs = processor(
        text=TEXT_QUERIES,
        images=image_rgb,
        return_tensors="pt"
    ).to(DEVICE)

    with torch.no_grad():
        outputs = model(**inputs)

    results = processor.post_process_object_detection(
        outputs,
        threshold=THRESHOLD,
        target_sizes=torch.tensor([[H, W]]).to(DEVICE)
    )[0]

    best_box, best_area = None, 0
    total_boxes = len(results["boxes"])

    for box in results["boxes"]:
        x1, y1, x2, y2 = box.int().tolist()
        bw, bh = x2 - x1, y2 - y1
        area = bw * bh
        aspect = bw / (bh + 1e-6)

        if area > 0.6 * H * W:
            pass
        elif area > 0.05 * H * W and 1.3 < aspect < 2.8:
            pass
        else:
            continue

        if area > best_area:
            best_area = area
            best_box = (x1, y1, x2, y2)

    latency = time.perf_counter() - start
    logger.info(
        f"[RUN {run_id}] OWL-ViT detection completed in {latency:.3f}s"
        f" - Found {total_boxes} boxes, Best box: {best_box}"
    )

    if best_box is not None:
        x1, y1, x2, y2 = best_box
        best_box = (max(0, x1), max(0, y1), min(W, x2), min(H, y2))

    return best_box


def crop_from_box(image_rgb, box, run_id: int):
    start = time.perf_counter()
    if box is None:
        logger.info(f"[RUN {run_id}] No box provided for cropping")
        return None

    x1, y1, x2, y2 = box
    roi = image_rgb[y1:y2, x1:x2]
    result = roi if roi.size else None

    latency = time.perf_counter() - start
    logger.info(
        f"[RUN {run_id}] Cropping completed in {latency:.4f}s"
        f" - ROI size: {roi.shape if result is not None else 'None'}"
    )
    return result