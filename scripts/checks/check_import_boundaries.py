#!/usr/bin/env python3
import ast
import json
from fnmatch import fnmatch
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
RULES_PATH = ROOT / "scripts" / "checks" / "import_boundary_rules.json"


def load_rules() -> dict:
    with RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def iter_python_files(rules: dict) -> list[Path]:
    files: list[Path] = []
    for root_name in rules.get("scan_roots", []):
        base = ROOT / root_name
        if base.exists():
            files.extend(sorted(base.rglob("*.py")))
    for single_name in rules.get("scan_files", []):
        single = ROOT / single_name
        if single.exists():
            files.append(single)
    for glob_pattern in rules.get("scan_globs", []):
        files.extend(sorted(ROOT.glob(glob_pattern)))
    return sorted(set(files))


def module_targets(node: ast.AST) -> list[str]:
    targets: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            targets.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            targets.append(node.module)
    return targets


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def starts_with_any(value: str, prefixes: tuple[str, ...] | list[str]) -> bool:
    return any(value == p or value.startswith(f"{p}.") for p in prefixes)


def path_matches_rule(relative_path: str, rule: dict) -> bool:
    match = rule.get("match", {})
    prefixes = match.get("path_prefixes", [])
    exacts = set(match.get("path_exact", []))
    globs = match.get("path_globs", [])
    return (
        any(relative_path.startswith(prefix) for prefix in prefixes)
        or relative_path in exacts
        or any(fnmatch(relative_path, pattern) for pattern in globs)
    )


def check_rule_for_import(relative_path: str, target: str, rule: dict) -> str | None:
    if not path_matches_rule(relative_path, rule):
        return None
    forbidden_prefixes = rule.get("forbidden_import_prefixes", [])
    if starts_with_any(target, forbidden_prefixes):
        message = rule.get("message", "Import boundary violated.")
        return (
            f"{relative_path} imports '{target}' which crosses '{rule.get('name', 'unnamed')}' boundary. "
            f"{message}"
        )
    return None


def main() -> int:
    rules = load_rules()
    violations: list[str] = []
    for file_path in iter_python_files(rules):
        relative_path = rel(file_path)
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        for node in ast.walk(tree):
            for target in module_targets(node):
                for rule in rules.get("rules", []):
                    violation = check_rule_for_import(relative_path, target, rule)
                    if violation:
                        violations.append(violation)

    if violations:
        print("Import boundary violations detected:")
        for violation in sorted(set(violations)):
            print(f"- {violation}")
        return 1
    print("Import boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
