from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

EXCLUDED_PARTS = frozenset(
	{
		".artifacts",
		".git",
		".mypy_cache",
		".pyright",
		".pytest_cache",
		".ruff_cache",
		".venv",
		"__pycache__",
		"build",
		"dist",
		"htmlcov",
		"node_modules",
		"venv",
	}
)
MANIFEST_NAME = "SHA256SUMS.txt"


def repository_files(root: Path):
	for path in sorted(root.rglob("*")):
		if not path.is_file() or path.name in {MANIFEST_NAME, ".eslintcache"}:
			continue
		if any(part in EXCLUDED_PARTS for part in path.parts):
			continue
		if path.suffix in {".pyc", ".pyo"}:
			continue
		yield path


def calculate(root: Path) -> dict[str, str]:
	return {
		path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
		for path in repository_files(root)
	}


def write_manifest(root: Path) -> None:
	rows = calculate(root)
	content = "".join(f"{digest}  {path}\n" for path, digest in rows.items())
	(root / MANIFEST_NAME).write_text(content, encoding="utf-8", newline="\n")


def verify_manifest(root: Path) -> list[str]:
	manifest = root / MANIFEST_NAME
	if not manifest.is_file():
		return [f"missing {MANIFEST_NAME}"]
	expected: dict[str, str] = {}
	for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
		if not line:
			continue
		try:
			digest, path = line.split("  ", 1)
		except ValueError:
			return [f"invalid checksum row at line {line_number}"]
		expected[path] = digest

	actual = calculate(root)
	violations = [
		f"checksum mismatch: {path}"
		for path in sorted(expected.keys() & actual.keys())
		if expected[path] != actual[path]
	]
	violations.extend(f"missing file: {path}" for path in sorted(expected.keys() - actual.keys()))
	violations.extend(
		f"untracked by checksum manifest: {path}" for path in sorted(actual.keys() - expected.keys())
	)
	return violations


def main() -> int:
	parser = argparse.ArgumentParser(description="Write or verify the repository SHA-256 manifest.")
	parser.add_argument("--write", action="store_true", help="Regenerate SHA256SUMS.txt.")
	args = parser.parse_args()
	root = Path(__file__).resolve().parents[1]
	if args.write:
		write_manifest(root)
		print(f"wrote {MANIFEST_NAME}")
		return 0
	violations = verify_manifest(root)
	if violations:
		for violation in violations:
			print(violation, file=sys.stderr)
		return 1
	print(f"{MANIFEST_NAME} verified")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
