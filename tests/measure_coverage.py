"""Prints statement coverage of modules/ for the test suite. Run inside Blender:
blender -b --factory-startup --python tests/measure_coverage.py"""
import ast, os, sys, unittest
ROOT = os.getcwd()
sys.path.insert(0, ROOT)
MODS = os.path.join(ROOT, "modules")
executed = {}

def tracer(frame, event, arg):
    fn = frame.f_code.co_filename
    if fn.startswith(MODS):
        executed.setdefault(fn, set()).add(frame.f_lineno) if event == "line" else None
        return tracer
    return None

def statement_lines(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            lines.add(node.lineno)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            # the def line runs at import time; decorators and body start count too
            lines.add(node.lineno)
    # drop docstrings
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
                lines.discard(first.lineno)
    return lines

sys.settrace(tracer)
suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"), top_level_dir=ROOT)
import threading
result = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(suite)
sys.settrace(None)
print("tests run:", result.testsRun, "ok:", result.wasSuccessful())
total_s = total_hit = 0
for fn in sorted(os.listdir(MODS)):
    if not fn.endswith(".py"):
        continue
    p = os.path.join(MODS, fn)
    st = statement_lines(p)
    hit = st & executed.get(p, set())
    total_s += len(st); total_hit += len(hit)
    pct = 100 * len(hit) / len(st) if st else 100
    print(f"{fn:20s} {len(hit):4d}/{len(st):4d}  {pct:5.1f}%")
print(f"{'TOTAL':20s} {total_hit:4d}/{total_s:4d}  {100*total_hit/total_s:5.1f}%")
