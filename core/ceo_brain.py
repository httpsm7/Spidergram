"""
core/ceo_brain.py
──────────────────
CEO Brain — Master Controller

Responsibilities:
  • Strategic decisions across all agents
  • Analyse performance and improve workflows
  • Respond to user requests (chat / dashboard)
  • Modify system code when instructed
  • Use Ollama primary / Grok fallback
"""

import json, re
import requests
from config.settings import OLLAMA_HOST, OLLAMA_MODEL
from integrations.grok import chat as grok_chat
from self_modify import (
    read_module, list_modules, get_module_summary,
    apply_modification, rollback,
)
from agents import (
    load_all_agents, list_agents, create_agent,
    edit_agent, delete_agent, set_agent_credentials,
)
from database.models import PostLog, Analytics, TaskQueue, db
from utils import get_logger, set_key, list_keys

logger = get_logger("core.ceo_brain")

CEO_SYSTEM = """
You are the CEO Brain of Spidergram — an autonomous multi-agent Instagram news automation system.

Your capabilities:
1. Create, edit, delete agents via tool calls
2. Analyse performance data and adjust strategy
3. Modify Python modules when user requests improvements
4. Manage API keys securely
5. Respond to user commands intelligently

When you need to call a tool, output a JSON block like:
<tool>{"name": "tool_name", "args": {...}}</tool>

Available tools:
- list_agents: {}
- create_agent: {"name": str, "niche": str, "prompt": str, "keywords": list}
- edit_agent: {"agent_id": str, "updates": dict}
- delete_agent: {"agent_id": str}
- set_credentials: {"agent_id": str, "ig_user_id": str, "access_token": str}
- set_api_key: {"name": str, "value": str}
- list_api_keys: {}
- read_module: {"path": str}
- modify_module: {"path": str, "instruction": str}
- rollback_module: {"path": str}
- run_agent: {"agent_id": str}
- performance_report: {}
- list_modules: {}

Always think step-by-step. Be decisive, helpful, and technically precise.
"""


def _ollama_chat(messages: list[dict]) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages,
                  "stream": False, "options": {"temperature": 0.7}},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning(f"Ollama failed: {exc} — trying Grok.")
        return ""


def _llm(messages: list[dict]) -> str:
    result = _ollama_chat(messages)
    if not result:
        result = grok_chat(messages)
    return result or "I could not process that request (both AI backends unavailable)."


def _extract_tool_call(text: str) -> tuple[str, dict] | None:
    """Parse <tool>{...}</tool> block from LLM output."""
    match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("name"), data.get("args", {})
        except json.JSONDecodeError:
            pass
    return None


def _execute_tool(name: str, args: dict) -> str:
    """Execute a CEO tool call and return result string."""
    try:
        if name == "list_agents":
            return json.dumps(list_agents(), indent=2)

        elif name == "create_agent":
            a = create_agent(args["name"], args["niche"],
                             args["prompt"], args.get("keywords", []))
            return f"Agent created: {a.id}"

        elif name == "edit_agent":
            ok = edit_agent(args["agent_id"], args["updates"])
            return "Updated." if ok else "Agent not found."

        elif name == "delete_agent":
            ok = delete_agent(args["agent_id"])
            return "Deleted." if ok else "Not found."

        elif name == "set_credentials":
            ok = set_agent_credentials(args["agent_id"],
                                       args["ig_user_id"], args["access_token"])
            return "Credentials set." if ok else "Agent not found."

        elif name == "set_api_key":
            set_key(args["name"], args["value"])
            return f"Key stored: {args['name']}"

        elif name == "list_api_keys":
            return str(list_keys())

        elif name == "read_module":
            return read_module(args["path"])

        elif name == "list_modules":
            return get_module_summary()

        elif name == "modify_module":
            return _modify_module_flow(args["path"], args["instruction"])

        elif name == "rollback_module":
            ok, msg = rollback(args["path"])
            return msg

        elif name == "run_agent":
            from agents import get_agent
            agent = get_agent(args["agent_id"])
            if not agent:
                return "Agent not found."
            log = agent.run_pipeline()
            return f"Pipeline ran. Status: {log.status if log else 'no log'}"

        elif name == "performance_report":
            return _build_performance_report()

        else:
            return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool error: {exc}"


def _modify_module_flow(path: str, instruction: str) -> str:
    """Read module, ask LLM to improve it, apply changes."""
    try:
        current_code = read_module(path)
    except FileNotFoundError as exc:
        return str(exc)

    messages = [
        {"role": "system", "content":
            "You are an expert Python engineer. "
            "You will be given a module's source code and an improvement instruction. "
            "Return ONLY the complete, modified Python file with no markdown fences."
        },
        {"role": "user", "content":
            f"Module: {path}\n\n"
            f"Instruction: {instruction}\n\n"
            f"Current code:\n{current_code}"
        },
    ]
    new_code = _llm(messages)
    ok, msg  = apply_modification(path, new_code)
    return msg


def _build_performance_report() -> str:
    """Summarise post analytics for the CEO."""
    with db:
        total   = PostLog.select().count()
        success = PostLog.select().where(PostLog.status == "success").count()
        failed  = PostLog.select().where(PostLog.status == "failed").count()
    return (
        f"Performance Report:\n"
        f"  Total posts: {total}\n"
        f"  Succeeded:   {success}\n"
        f"  Failed:      {failed}\n"
        f"  Success rate:{round(success/max(total,1)*100,1)}%"
    )


class CEOBrain:
    def __init__(self):
        self.conversation: list[dict] = [
            {"role": "system", "content": CEO_SYSTEM}
        ]
        load_all_agents()
        logger.info("CEO Brain initialised.")

    def chat(self, user_message: str) -> str:
        """
        Main entry point for chat interaction.
        Processes user message, optionally calls tools, returns final reply.
        """
        self.conversation.append({"role": "user", "content": user_message})
        raw_reply = _llm(self.conversation)

        # Check for tool call
        tool_result = ""
        tool = _extract_tool_call(raw_reply)
        if tool:
            tool_name, tool_args = tool
            logger.info(f"CEO tool call: {tool_name}({tool_args})")
            tool_result  = _execute_tool(tool_name, tool_args)
            # Feed tool result back for final reply
            self.conversation.append({"role": "assistant", "content": raw_reply})
            self.conversation.append({"role": "user",
                                       "content": f"Tool result: {tool_result}"})
            final_reply = _llm(self.conversation)
        else:
            final_reply = raw_reply

        # Trim conversation history to last 20 messages
        if len(self.conversation) > 22:
            system_msg         = self.conversation[0]
            self.conversation  = [system_msg] + self.conversation[-20:]

        self.conversation.append({"role": "assistant", "content": final_reply})
        return final_reply

    def quick_command(self, command: str, args: dict = None) -> str:
        """Execute a direct tool call without full conversation context."""
        return _execute_tool(command, args or {})
