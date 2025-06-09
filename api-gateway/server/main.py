import os
import uvicorn
from src.api.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 12000))
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )