import os
import sys

# Ensure root workspace directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from app.main import app
except Exception as e:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    err_msg = traceback.format_exc()
    print("Vercel Startup Error:", err_msg)

    app = FastAPI(title="GDKTPL Fallback")

    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def catch_all(path_name: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Lỗi khởi động Serverless Function",
                "error": str(e),
                "traceback": err_msg
            }
        )
