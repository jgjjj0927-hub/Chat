import os
import sys
import uvicorn

# чтобы exe находил пакет server рядом с собой
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.main import app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
