import base64
import json
import tempfile
import time
import filetype
from fastapi import HTTPException
from router.logger import logger


def decode_base64_to_file(base64_string: str, run_id: int):
    start = time.perf_counter()
    logger.info(f"[RUN {run_id}] Starting Base64 decoding")

    content = base64_string.strip().encode()

    if b"base64," in content:
        logger.info(f"[RUN {run_id}] Base64 header detected and removed")
        content = content.split(b"base64,")[1]

    try:
        decoded_data = base64.b64decode(content, validate=True)
    except Exception:
        logger.error(f"[RUN {run_id}] Invalid Base64 input")
        raise HTTPException(status_code=400, detail="Invalid Base64 input")

    # ================= CHECK IF JSON =================
    try:
        decoded_text = decoded_data.decode("utf-8").strip()
        if decoded_text.startswith("{") or decoded_text.startswith("["):
            logger.info(f"[RUN {run_id}] Decoded content is JSON")
            json_data = json.loads(decoded_text)

            def find_large_base64(obj):
                if isinstance(obj, dict):
                    for v in obj.values():
                        result = find_large_base64(v)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_large_base64(item)
                        if result:
                            return result
                elif isinstance(obj, str):
                    try:
                        candidate = obj.strip().encode()
                        decoded_candidate = base64.b64decode(candidate, validate=True)
                        if len(decoded_candidate) > 500:
                            return obj
                    except Exception:
                        pass
                return None

            nested = find_large_base64(json_data)
            if nested:
                logger.info(f"[RUN {run_id}] Valid nested Base64 found → decoding again")
                return decode_base64_to_file(nested, run_id)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            tmp.write(decoded_data)
            tmp.close()

            latency = time.perf_counter() - start
            logger.info(f"[RUN {run_id}] JSON saved as file in {latency:.3f}s - Path: {tmp.name}")
            return tmp.name, "json", len(decoded_data)

    except UnicodeDecodeError:
        pass
    except json.JSONDecodeError:
        pass

    # ================= FILE SIGNATURE DETECTION =================
    if decoded_data.startswith(b"\xff\xd8"):
        extension = "jpg"
    elif decoded_data.startswith(b"\x89PNG"):
        extension = "png"
    elif decoded_data.startswith(b"%PDF"):
        extension = "pdf"
    elif decoded_data.startswith(b"RIFF") and b"WEBP" in decoded_data[:20]:
        extension = "webp"
    else:
        kind = filetype.guess(decoded_data)
        extension = kind.extension if kind else None

    if not extension:
        logger.error(f"[RUN {run_id}] Unable to detect file type")
        raise HTTPException(status_code=400, detail="Unsupported or corrupted base64 file")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}")
    tmp.write(decoded_data)
    tmp.close()

    latency = time.perf_counter() - start
    logger.info(f"[RUN {run_id}] Base64 decoding completed in {latency:.3f}s - Saved to {tmp.name}")
    return tmp.name, extension, len(decoded_data)