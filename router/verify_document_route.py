import os
import base64
import json
import tempfile
import time

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path

from router.logger import logger
from router.document_detector import detect_best_box, crop_from_box
from router.document_classifier import detect_document_type_fuzzy
from router.field_extractor import extract_document_fields
from router.name_matcher import match_name
from router.encryption_handler import decrypt_enc_file, save_decrypted_temp_file
from router.document_processor import process_document

router = APIRouter()

API_KEY = os.getenv("x-api-key")


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()
    return request.client.host if request.client else "unknown"


@router.post("/verify-document", response_class=JSONResponse)
async def verify_document(
    request: Request,
    password: str = Form(None),
    file: UploadFile = File(None),
    document_type: str = Form(None),
    user_name: str = Form(None),
    x_api_key: str = Header(...),
):
    RUN_ID = int(time.time() * 1000)
    client_ip = get_client_ip(request)

    logger.info("=" * 80)
    logger.info(f"[RUN {RUN_ID}] NEW REQUEST RECEIVED")
    logger.info(f"[RUN {RUN_ID}] Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"[RUN {RUN_ID}] Client IP: {client_ip}")
    logger.info(f"[RUN {RUN_ID}]   - Document Type: {document_type}")
    logger.info(f"[RUN {RUN_ID}]   - User Name: {user_name}")
    logger.info("=" * 80)

    # ── Auth ──
    if x_api_key != API_KEY:
        logger.warning(f"[RUN {RUN_ID}] Authentication failed from IP: {client_ip}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    logger.info(f"[RUN {RUN_ID}] Authentication successful")

    if file is None:
        raise HTTPException(status_code=400, detail="File upload required (.enc, image, or pdf)")

    if not document_type or not user_name:
        raise HTTPException(status_code=400, detail="document_type and user_name required")

    file_path = None

    try:
        original_filename = file.filename
        file_content = await file.read()
        original_extension = file.filename.lower().split(".")[-1]

        logger.info(f"[RUN {RUN_ID}] Input Mode: Direct File Upload")

        # ── .enc decryption ──
        if original_extension == "enc":
            logger.info(f"[RUN {RUN_ID}] .enc file detected - Starting decryption")
            if not password:
                raise HTTPException(status_code=400, detail="Password required for .enc file")
            decrypted_bytes = decrypt_enc_file(file_content, password)
            file_path, extension = save_decrypted_temp_file(decrypted_bytes, RUN_ID)

        # ── Normal image / PDF ──
        else:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(file.filename)[1]
            ) as tmp:
                tmp.write(file_content)
                file_path = tmp.name
            extension = original_extension

        logger.info(f"[RUN {RUN_ID}] File extension: {extension}")

        # ── JSON ──
        if extension == "json":
            logger.info(f"[RUN {RUN_ID}] Processing as JSON document")
            with open(file_path, "r", encoding="utf-8") as f:
                ocr_text = f.read()

            detected, _ = detect_document_type_fuzzy(ocr_text, RUN_ID)
            name_ok, name_score = match_name(user_name, ocr_text, RUN_ID)
            fields = extract_document_fields(detected, ocr_text, RUN_ID)
            status_value = "success" if detected == document_type and name_ok else "failed"

            result = {
                "input": {
                    "file_name": original_filename,
                    "document_type": document_type,
                    "user_name": user_name
                },
                "status": status_value,
                "ocr": {"latency_seconds": 0, "text_preview": ocr_text},
                "verification": {
                    "document_type_detected": detected,
                    "name_match_score": round(name_score, 2),
                    "name_verified": name_ok,
                    "document_verified": detected == document_type
                },
                "extracted_fields": fields
            }

        # ── Image ──
        elif extension in ["jpg", "jpeg", "png", "webp"]:
            logger.info(f"[RUN {RUN_ID}] Processing as IMAGE file")
            img = cv2.imread(file_path)
            if img is None:
                raise HTTPException(status_code=400, detail="Invalid image file")

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            box = detect_best_box(img_rgb, RUN_ID)
            roi = crop_from_box(img_rgb, box, RUN_ID)

            roi_path = file_path
            if roi is not None:
                roi_path = os.path.splitext(file_path)[0] + "_roi.jpg"
                if not cv2.imwrite(roi_path, cv2.cvtColor(roi, cv2.COLOR_RGB2BGR)):
                    raise HTTPException(status_code=500, detail="Failed to save ROI image")

            result = process_document(roi_path, original_filename, document_type, user_name, RUN_ID)

        # ── PDF ──
        elif extension == "pdf":
            logger.info(f"[RUN {RUN_ID}] Processing as PDF file")
            pages = convert_from_path(file_path, dpi=180)
            img_rgb = np.array(pages[0])

            box = detect_best_box(img_rgb, RUN_ID)
            roi = crop_from_box(img_rgb, box, RUN_ID)

            roi_path = os.path.splitext(file_path)[0] + "_page_1.jpg"
            img_to_save = cv2.cvtColor(roi if roi is not None else img_rgb, cv2.COLOR_RGB2BGR)
            if not cv2.imwrite(roi_path, img_to_save):
                raise HTTPException(status_code=500, detail="Failed to save PDF page image")

            result = process_document(roi_path, original_filename, document_type, user_name, RUN_ID)

        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        result_base64 = base64.b64encode(json.dumps(result).encode()).decode()
        return {"normal_response": result, "base64_response": result_base64}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RUN {RUN_ID}] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"[RUN {RUN_ID}] Temporary file cleaned up: {file_path}")