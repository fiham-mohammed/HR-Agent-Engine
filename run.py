"""Launcher for ZeloraTech HR Engine.

Run with:
    python run.py

This file checks required modules first. If anything important is missing,
it installs packages from requirements.txt using the same Python interpreter
that is running this file, then starts the FastAPI server.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"

# import_name -> pip package name
REQUIRED_IMPORTS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "dotenv": "python-dotenv",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "langgraph": "langgraph",
    "langchain": "langchain",
    "langchain_community": "langchain-community",
    "httpx": "httpx",
    "anyio": "anyio",
}


def _missing_packages() -> list[str]:
    """Return pip package names for required modules that are not installed."""
    missing: list[str] = []
    for import_name, package_name in REQUIRED_IMPORTS.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(package_name)
    return missing


def ensure_dependencies() -> None:
    """Install requirements automatically if required modules are missing."""
    missing = _missing_packages()
    if not missing:
        return

    print("Missing Python modules detected:", ", ".join(sorted(set(missing))))
    print("Installing required packages. Please keep this window open...")

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        if REQUIREMENTS_FILE.exists():
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *sorted(set(missing))])
    except subprocess.CalledProcessError as exc:
        print("\nDependency installation failed.")
        print("Please run this command manually from the project folder:")
        print(f'  "{sys.executable}" -m pip install -r requirements.txt')
        raise SystemExit(exc.returncode) from exc


def main() -> None:
    ensure_dependencies()

    # Imports happen after auto-install, so run.py will not crash on line 1.
    import uvicorn
    from dotenv import load_dotenv

    os.chdir(ROOT)
    load_dotenv(ROOT / ".env")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    print(f"Starting ZeloraTech HR Engine on http://{host}:{port}")
    print(f"Swagger docs: http://{host}:{port}/docs")
    uvicorn.run("main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
