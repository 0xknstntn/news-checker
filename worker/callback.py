from langchain.callbacks.base import BaseCallbackHandler
from datetime import datetime
from pprint import pprint
import re

try:
        from colorama import init, Fore, Style
        init(autoreset=True)
        COLOR = True
except ImportError:
        COLOR = False

def _color(text, color):
        if not COLOR:
                return text
        return getattr(Fore, color.upper(), "") + str(text) + Style.RESET_ALL

def extract_user_question(inputs):
        match = re.search(r"<USER_QUESTION>(.*?)</USER_QUESTION>", inputs["user"], re.DOTALL)
        if match:
                return match.group(1).strip()
        return ""

class PrettyVerboseCallbackHandler(BaseCallbackHandler):
        def on_chain_start(self, serialized, inputs, **kwargs):
                print("\n")
                print(_color("="*40, "cyan"))
                print(_color(f"=== Agent Started [{datetime.now().strftime('%H:%M:%S')}] ===", "cyan"))
                print(_color(f"User input: {extract_user_question(inputs)}", "white"))

        def on_agent_action(self, action, **kwargs):
                print(_color(f"\n--- Step [{action.tool}] ---", "yellow"))
                print(_color(f"Input:", "green"), end=" ")
                pprint(action.tool_input)
                print(_color(f"Raw Log:\n{action.log}", "magenta"))

        def on_tool_end(self, output, **kwargs):
                print(_color(f"Tool output:", "blue"))
                if isinstance(output, dict) or isinstance(output, list):
                        pprint(output)
                else:
                        print(output)

        def on_agent_finish(self, finish, **kwargs):
                print(_color(f"\n=== Agent Finished ===", "cyan"))
                print(_color(f"Final output: {finish.return_values}", "white"))
                print()

        def on_chain_end(self, outputs, **kwargs):
                print(_color(f"All outputs:", "green"))
                pprint(outputs)
                print(_color("="*40, "cyan"))

        def on_chain_error(self, error, **kwargs):
                print(_color(f"\n[ERROR]: {error}", "red"))
