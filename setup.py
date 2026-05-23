#!/usr/bin/env python3
"""
ZeloraTech HR Agent Engine — auto-setup script.

Run this once to:
  1. Create (or reuse) a Python virtual environment
  2. Install all required packages
  3. Copy .env.example -> .env if no .env exists yet
  4. Initialise the SQLite database
  5. Run the test suite to verify everything is working

Usage:
    python setup.py
"""

import sys
import os
import subprocess
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
REQ_FILE = os.path.join(ROOT, "requirements.txt")
ENV_FILE = os.path.join(ROOT, ".env")
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")


def run(cmd, **kwargs):
    """Run a shell command, stream output, and raise on failure."""
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def python_in_venv():
    """Returns the path to the Python interpreter inside the venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def pip_in_venv():
    """Returns the path to pip inside the venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    return os.path.join(VENV_DIR, "bin", "pip")


def pytest_in_venv():
    """Returns the path to pytest inside the venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "pytest.exe")
    return os.path.join(VENV_DIR, "bin", "pytest")


def main():
    print("=" * 60)
    print("  ZeloraTech HR Agent Engine — Auto Setup")
    print("=" * 60)

    # 1. Create virtual environment if it doesn't exist
    if not os.path.isdir(VENV_DIR):
        print("\n[1/5] Creating virtual environment...")
        run([sys.executable, "-m", "venv", VENV_DIR])
    else:
        print("\n[1/5] Virtual environment already exists — skipping creation.")

    # 2. Upgrade pip silently, then install requirements
    print("\n[2/5] Installing dependencies from requirements.txt...")
    run([python_in_venv(), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    run([python_in_venv(), "-m", "pip", "install", "-r", REQ_FILE])

    # 3. Copy .env.example -> .env if .env is missing
    print("\n[3/5] Configuring environment file...")
    if not os.path.exists(ENV_FILE):
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        print("  Copied .env.example -> .env  (edit it to add real API keys if needed)")
    else:
        print("  .env already exists — skipping.")

    # 4. Initialise the database
    print("\n[4/5] Initialising SQLite database...")
    init_script = (
        "import sys, os; "
        "sys.path.insert(0, os.path.dirname(os.path.abspath('.')));"
        "from dotenv import load_dotenv; load_dotenv();"
        "from database.db import init_db; init_db();"
        "print('  Database initialised successfully.')"
    )
    run([python_in_venv(), "-c", init_script], cwd=ROOT)

    # 5. Run the test suite
    print("\n[5/5] Running test suite...")
    run([pytest_in_venv(), "test_main.py", "-v"], cwd=ROOT)

    print("\n" + "=" * 60)
    print("  Setup complete!")
    print(f"  Start the server with:  start_server.bat  (Windows)")
    print(f"  Or use the venv Python:  {python_in_venv()} run.py")
    print(f"  API docs:               http://127.0.0.1:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    main()
