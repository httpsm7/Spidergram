"""
ui/chat_interface/chat.py
──────────────────────────
Interactive terminal chat with the CEO Brain.
Supports multi-turn conversation and live tool execution.
"""

import sys
from core.ceo_brain import CEOBrain
from utils import get_logger, set_key

logger = get_logger("ui.chat")

WELCOME = """
╔═══════════════════════════════════════════╗
║     🕷  SPIDERGRAM — CEO Brain Chat       ║
║  Type your command or question below.     ║
║  Type 'exit' or Ctrl-C to quit.           ║
╚═══════════════════════════════════════════╝
"""

EXAMPLES = """
Example commands:
  • Create a new agent for cricket news
  • Show me all agents
  • Set NewsAPI key to abc123
  • Run the world_news agent pipeline
  • Improve video quality in the video engine
  • Show performance report
  • Edit india_politics agent prompt
"""


def run_chat(brain: CEOBrain = None) -> None:
    """Run the interactive terminal chat loop."""
    if brain is None:
        brain = CEOBrain()

    print(WELCOME)
    print(EXAMPLES)

    while True:
        try:
            user_input = input("\n🧑 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("CEO Brain: Shutting down chat. Goodbye!")
            break

        # Shortcut: adding API keys via chat
        if user_input.lower().startswith("set ") and " key " in user_input.lower():
            parts = user_input.split()
            # "Set NewsAPI key to VALUE"
            try:
                idx   = [p.lower() for p in parts].index("to")
                value = " ".join(parts[idx+1:])
                name  = "_".join(parts[1:-2]).upper() + "_KEY"
                set_key(name, value)
                print(f"🤖 CEO Brain: ✅ {name} stored securely.")
                continue
            except (ValueError, IndexError):
                pass

        print("\n🤖 CEO Brain: thinking…", end="\r")
        reply = brain.chat(user_input)
        print(f"\n🤖 CEO Brain: {reply}")


if __name__ == "__main__":
    run_chat()
