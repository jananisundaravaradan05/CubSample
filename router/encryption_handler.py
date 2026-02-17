import logging
import tempfile
import filetype
from fastapi import HTTPException
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger("documentclassifier")


def derive_key(password: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(password)


def decrypt_enc_file(enc_bytes: bytes, password: str) -> bytes:
    try:
        salt = enc_bytes[:16]
        iv = enc_bytes[16:28]
        ciphertext = enc_bytes[28:]
        key = derive_key(password.encode(), salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(iv, ciphertext, None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid password or corrupted .enc file")


def save_decrypted_temp_file(decrypted_bytes: bytes, run_id: int):
    if decrypted_bytes.startswith(b"\xff\xd8"):
        extension = "jpg"
    elif decrypted_bytes.startswith(b"\x89PNG"):
        extension = "png"
    elif decrypted_bytes.startswith(b"%PDF"):
        extension = "pdf"
    elif decrypted_bytes.startswith(b"RIFF") and b"WEBP" in decrypted_bytes[:20]:
        extension = "webp"
    else:
        kind = filetype.guess(decrypted_bytes)
        extension = kind.extension if kind else None

    if not extension:
        raise HTTPException(status_code=400, detail="Unsupported decrypted file type")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}")
    tmp.write(decrypted_bytes)
    tmp.close()

    logger.info(f"[RUN {run_id}] Decrypted file saved as {tmp.name}")
    return tmp.name, extension