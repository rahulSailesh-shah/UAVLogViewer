import uvicorn
import os

if __name__ == "__main__":
    environment = os.getenv("ENVIRONMENT", "development")
    is_development = environment == "development"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=is_development,
        # Increase timeout for large file uploads
        timeout_keep_alive=300,  # 5 minutes
        limit_max_requests=1000,
        limit_concurrency=100,
        reload_excludes=[
            "uploads/*",
            "*.log",
            "*.tmp",
            "__pycache__/*",
            ".git/*",
            "processed/*",
        ] if is_development else None,
        reload_includes=["*.py"] if is_development else None
    )
