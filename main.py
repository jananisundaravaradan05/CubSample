import os

os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from router.verify_document_route import router

app = FastAPI(title="Document Verification API")
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)