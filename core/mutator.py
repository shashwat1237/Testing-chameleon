# core/mutator.py
# Small, necessary fixes:
# - Writes runtime mutated server to /tmp/active_server.py (Render writable)
# - Writes mutation_state.json atomically to /tmp/mutation_state.json
# - Still attempts to write project output (best-effort) for local convenience
# - Preserves original AST mutation logic exactly

import ast
import secrets
import string
import os
import json
import traceback
from typing import Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(BASE_DIR, "target_app", "template.py")
PROJECT_OUTPUT_PATH = os.path.join(BASE_DIR, "target_app", "active_server.py")  # best-effort local write
RUNTIME_OUTPUT_PATH = "/tmp/active_server.py"  # Render-safe runtime
STATE_PATH = "/tmp/mutation_state.json"       # Render-safe JSON state

def generate_chaos_string(length=6):
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

class ChaosTransformer(ast.NodeTransformer):
    def __init__(self):
        self.route_map: Dict[str, str] = {}

    def visit_FunctionDef(self, node):
        if not node.decorator_list:
            return node

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and hasattr(decorator.func, 'attr'):
                if decorator.func.attr in ['get', 'post', 'put', 'delete']:
                    if decorator.args and hasattr(decorator.args[0], 'value'):
                        original_path = decorator.args[0].value

                        if original_path == "/":
                            self.route_map[original_path] = original_path
                            return node

                        mutation_hash = generate_chaos_string()
                        new_path = f"{original_path}_{mutation_hash}"
                        new_func_name = f"{node.name}_{mutation_hash}"

                        self.route_map[original_path] = new_path

                        decorator.args[0].value = new_path
                        node.name = new_func_name

        return node

def _atomic_write(path: str, content: str, mode: str = "w", encoding: str = "utf-8"):
    tmp = f"{path}.tmp"
    with open(tmp, mode, encoding=encoding) as f:
        f.write(content)
    os.replace(tmp, path)  # atomic on POSIX

def run_mutation():
    if not os.path.exists(TEMPLATE_PATH):
        print(f"[MUTATOR][ERROR] Template not found at {TEMPLATE_PATH}")
        return {}

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as src:
        tree = ast.parse(src.read())

    transformer = ChaosTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    mutated_source = ast.unparse(new_tree)

    # Best-effort local write (may fail on Render; non-fatal)
    try:
        with open(PROJECT_OUTPUT_PATH, "w", encoding="utf-8") as dst:
            dst.write(mutated_source)
        print(f"[MUTATOR] Wrote local project output -> {PROJECT_OUTPUT_PATH}")
    except Exception as e:
        print(f"[MUTATOR] Skipped local write: {e}")

    # Write runtime mutated server to /tmp (use atomic write)
    try:
        _atomic_write(RUNTIME_OUTPUT_PATH, mutated_source)
        print(f"[MUTATOR] Wrote runtime output -> {RUNTIME_OUTPUT_PATH}")
    except Exception as e:
        print(f"[MUTATOR][ERROR] Failed to write runtime output: {e}")
        print(traceback.format_exc())

    # Save route map as JSON atomically to /tmp
    try:
        json_text = json.dumps(transformer.route_map, indent=4)
        _atomic_write(STATE_PATH, json_text)
        print(f"[MUTATOR] State saved -> {STATE_PATH}")
    except Exception as e:
        print(f"[MUTATOR][ERROR] Failed writing state: {e}")
        print(traceback.format_exc())

    return transformer.route_map

if __name__ == "__main__":
    print(run_mutation())
