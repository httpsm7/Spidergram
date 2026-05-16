"""
install.py
───────────
Spidergram v2 — One-command Installer

Run: python install.py

Steps:
  1. Check Python version
  2. Check / install Ollama
  3. Pull required Ollama models
  4. Create virtual environment
  5. Install Python dependencies
  6. Initialise database
  7. Register Modelfiles with Ollama
  8. Generate encryption key
  9. Create .env from template
  10. Print next-steps guide
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

BASE = Path(__file__).parent
VENV = BASE / "venv"
PIP  = VENV / "bin" / "pip" if os.name != "nt" else VENV / "Scripts" / "pip"
PY   = VENV / "bin" / "python" if os.name != "nt" else VENV / "Scripts" / "python"

RED   = "\033[91m"
GREEN = "\033[92m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def ok(msg):  print(f"  {GREEN}✅{RESET} {msg}")
def info(msg):print(f"  {CYAN}ℹ {RESET} {msg}")
def err(msg): print(f"  {RED}❌{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{CYAN}{'─'*50}\n  {msg}\n{'─'*50}{RESET}")


def check_python():
    header("Step 1: Python Version")
    v = sys.version_info
    if v.major < 3 or v.minor < 10:
        err(f"Python 3.10+ required. Found: {v.major}.{v.minor}")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def check_ollama():
    header("Step 2: Ollama Check")
    if shutil.which("ollama"):
        ok("Ollama already installed.")
        return
    info("Ollama not found. Installing…")
    if sys.platform.startswith("linux"):
        os.system("curl -fsSL https://ollama.com/install.sh | sh")
        ok("Ollama installed.")
    elif sys.platform == "darwin":
        info("Download Ollama from https://ollama.com/download and install manually.")
        input("Press Enter when done…")
    else:
        info("Download Ollama from https://ollama.com/download/windows")
        input("Press Enter when done…")


def start_ollama():
    header("Step 3: Start Ollama Service")
    try:
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time; time.sleep(3)
        ok("Ollama service started.")
    except Exception as exc:
        info(f"Could not auto-start Ollama: {exc}")
        info("Run 'ollama serve' in a separate terminal.")


def pull_models():
    header("Step 4: Pull Ollama Models")
    model = "gemma3"
    info(f"Pulling {model} (this may take a few minutes)…")
    result = subprocess.run(["ollama", "pull", model], capture_output=False)
    if result.returncode == 0:
        ok(f"{model} ready.")
    else:
        err(f"Failed to pull {model}. Run: ollama pull {model}")


def create_venv():
    header("Step 5: Python Virtual Environment")
    if VENV.exists():
        ok("venv already exists.")
        return
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    ok(f"venv created at {VENV}")


def install_deps():
    header("Step 6: Install Python Dependencies")
    subprocess.run([str(PIP), "install", "--upgrade", "pip", "-q"], check=True)
    subprocess.run([str(PIP), "install", "-r", str(BASE / "requirements.txt"), "-q"], check=True)
    ok("All dependencies installed.")


def init_database():
    header("Step 7: Initialise Database")
    sys.path.insert(0, str(BASE))
    try:
        from database.models import init_db
        init_db()
        ok("Database ready at data/db/spidergram.db")
    except Exception as exc:
        err(f"DB init failed: {exc}")


def register_modelfiles():
    header("Step 8: Register Persona Modelfiles")
    mf_dir = BASE / "modelfiles"
    for mf in mf_dir.glob("*.Modelfile"):
        name   = mf.stem
        result = subprocess.run(
            ["ollama", "create", name, "-f", str(mf)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            ok(f"Model registered: {name}")
        else:
            err(f"{name} failed: {result.stderr.strip()[:80]}")


def generate_encryption_key():
    header("Step 9: Generate Encryption Key")
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        env_path = BASE / ".env"
        if env_path.exists():
            content = env_path.read_text()
            if "ENCRYPTION_KEY=" in content:
                ok("Encryption key already in .env")
                return
        with open(env_path, "a") as f:
            f.write(f"\nENCRYPTION_KEY={key}\n")
        ok(f"Encryption key generated and saved to .env")
    except Exception as exc:
        err(f"Could not generate key: {exc}")


def create_env():
    header("Step 10: Environment File")
    env_src  = BASE / ".env.example"
    env_dest = BASE / ".env"
    if env_dest.exists():
        ok(".env already exists — skipping copy.")
    else:
        shutil.copy(env_src, env_dest)
        ok(".env created from .env.example")
    info("Edit .env and add your API keys, OR use the web dashboard.")


def print_next_steps():
    print(f"""
{BOLD}{GREEN}{'═'*50}
  🕷  Spidergram v2 Installation Complete!
{'═'*50}{RESET}

{BOLD}Next steps:{RESET}

  1. Edit your credentials:
     nano .env
     (or add keys via the dashboard at http://localhost:7111/keys)

  2. Configure Instagram accounts:
     Edit config/agents.json
     Add ig_user_id and access_token per agent.

  3. Start Spidergram:
     source venv/bin/activate
     python main.py --both            # scheduler + dashboard

  4. Open the dashboard:
     http://localhost:7111

  5. Chat with CEO Brain:
     python main.py --chat

  6. Test without posting:
     python main.py --dry-run

{CYAN}Tip: Use 'python main.py --help' for all options.{RESET}
""")


if __name__ == "__main__":
    print(f"\n{BOLD}🕷  Spidergram v2 Installer{RESET}\n")
    check_python()
    check_ollama()
    start_ollama()
    pull_models()
    create_venv()
    install_deps()
    init_database()
    register_modelfiles()
    generate_encryption_key()
    create_env()
    print_next_steps()
