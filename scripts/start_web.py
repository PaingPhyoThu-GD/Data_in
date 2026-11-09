"""
Launcher for Gemini OCR Frontend & Middleware Server.
"""

from __future__ import annotations
import argparse
import sys
import webbrowser
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Gemini Myanmar-English OCR Web Frontend.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"\n=======================================================")
    print(f"  Starting Gemini Myanmar-English OCR Web Frontend")
    print(f"  URL: {url}")
    print(f"=======================================================\n")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(
        "frontend.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

