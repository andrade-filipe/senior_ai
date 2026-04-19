"""Entry point for uvicorn.

Run with:
    python -m scheduling_api
or:
    uv run python -m scheduling_api
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "scheduling_api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,  # Disable uvicorn default logging; we use JsonFormatter
    )
