# core/mutator.py
# This module is responsible for generating the mutated server at runtime.
# It reads the clean template, rewrites all routes using AST manipulation,
# and writes the mutated version both to the project directory (for local runs)
# and to /tmp, which is the safe writable location in cloud environments.

import ast
import secrets
import string
import os
import json
import traceback
from typing import Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(BASE_DIR, "target_app", "template.py")
PROJECT_OUTPUT_PATH = os.path.join(BASE_DIR, "target_app", "active_server.py")  # optional local output for convenience
RUNTIME_OUTPUT_PATH = "/tmp/active_server.py"  # primary executable output used by the running system
STATE_PATH = "/tmp/mutation_state.json"       # stores the latest route mapping

def generate_chaos_string(length=6):
    # Generates a short randomized suffix used to mutate endpoint paths.
    # Cryptographic randomness prevents predictable route structures.
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

class ChaosTransformer(ast.NodeTransformer):
    # Traverses the FastAPI template and rewrites decorated endpoints.
    # It tracks both original and mutated paths so the proxy can remap traffic.
    def __init__(self):
        self.route_map: Dict[str, str] = {}

    def visit_FunctionDef(self, node):
        # Only functions with route decorators are relevant to the mutation process.
        if not node.decorator_list:
            return node

        for decorator in node.decorator_list:
            # Detect typical FastAPI method decorators such as @app.get/post/etc.
            if isinstance(decorator, ast.Call) and hasattr(decorator.func, 'attr'):
                if decorator.func.attr in ['get', 'post', 'put', 'delete']:
                    if decorator.args and hasattr(decorator.args[0], 'value'):
                        original_path = decorator.args[0].value

                        # Keep the root endpoint stable for health checks and system probes.
                        if original_path == "/":
                            self.route_map[original_path] = original_path
                            return node

                        # Construct a mutated route and rename the associated function.
                        mutation_hash = generate_chaos_string()
                        new_path = f"{original_path}_{mutation_hash}"
                        new_func_name = f"{node.name}_{mutation_hash}"

                        self.route_map[original_path] = new_path

                        decorator.args[0].value = new_path
                        node.name = new_func_name

        return node

def _atomic_write(path: str, content: str, mode: str = "w", encoding: str = "utf-8"):
    # Ensures safe, atomic writes so partially written files never appear,
    # especially important in environments where multiple workers may restart.
    tmp = f"{path}.tmp"
    with open(tmp, mode, encoding=encoding) as f:
        f.write(content)
    os.replace(tmp, path)  # POSIX atomic file replacement

def run_mutation():
    # Load the base template; without this the system cannot continue.
    if not os.path.exists(TEMPLATE_PATH):
        print(f"[MUTATOR][ERROR] Template not found at {TEMPLATE_PATH}")
        return {}

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as src:
        tree = ast.parse(src.read())

    # Apply the mutation logic and produce the updated AST.
    transformer = ChaosTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    mutated_source = ast.unparse(new_tree)

    # Write a local copy to the project folder for developers running the system manually.
    try:
        with open(PROJECT_OUTPUT_PATH, "w", encoding="utf-8") as dst:
            dst.write(mutated_source)
        print(f"[MUTATOR] Wrote local project output -> {PROJECT_OUTPUT_PATH}")
    except Exception as e:
        print(f"[MUTATOR] Skipped local write: {e}")

    # The main runtime output lives in /tmp, which is always writable in cloud environments.
    try:
        _atomic_write(RUNTIME_OUTPUT_PATH, mutated_source)
        print(f"[MUTATOR] Wrote runtime output -> {RUNTIME_OUTPUT_PATH}")
    except Exception as e:
        print(f"[MUTATOR][ERROR] Failed to write runtime output: {e}")
        print(traceback.format_exc())

    # Persist the route mapping so the proxy can correctly forward incoming requests.
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
