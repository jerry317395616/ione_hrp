from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLAN_BLOCKED_EXIT = 3
ENABLED_FIELDS = {
	"allow_deletions",
	"allow_force_pushes",
	"allow_fork_syncing",
	"block_creations",
	"enforce_admins",
	"lock_branch",
	"required_conversation_resolution",
	"required_linear_history",
}


class GitHubAPIError(RuntimeError):
	def __init__(self, returncode: int, output: str):
		super().__init__(output.strip())
		self.returncode = returncode
		self.output = output.strip()


def load_policy(path: Path) -> dict[str, Any]:
	payload = json.loads(path.read_text(encoding="utf-8"))
	if not payload.get("repository"):
		raise ValueError("branch policy must declare repository")
	if not payload.get("default_branch"):
		raise ValueError("branch policy must declare default_branch")
	if not isinstance(payload.get("protection"), dict):
		raise ValueError("branch policy must declare protection")
	return payload


def is_plan_blocker(message: str) -> bool:
	lowered = message.lower()
	return "upgrade to github pro" in lowered or "make this repository public" in lowered


def normalize_field(field: str, value: Any) -> Any:
	if field in ENABLED_FIELDS and isinstance(value, dict):
		return value.get("enabled")
	return value


def compare_protection(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
	mismatches: list[str] = []
	for field, expected_value in expected.items():
		actual_value = normalize_field(field, actual.get(field))
		if isinstance(expected_value, dict):
			if not isinstance(actual_value, dict):
				mismatches.append(f"{field}: expected object, got {actual_value!r}")
				continue
			for nested_field, nested_expected in expected_value.items():
				nested_actual = normalize_field(
					nested_field,
					actual_value.get(nested_field),
				)
				if nested_actual != nested_expected:
					mismatches.append(
						f"{field}.{nested_field}: expected {nested_expected!r}, got {nested_actual!r}"
					)
			continue
		if actual_value != expected_value:
			mismatches.append(f"{field}: expected {expected_value!r}, got {actual_value!r}")
	return mismatches


def run_gh_api(
	endpoint: str,
	*,
	method: str = "GET",
	payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
	command = ["gh", "api", endpoint]
	input_text = None
	if method != "GET":
		command.extend(["--method", method])
	if payload is not None:
		command.extend(["--input", "-"])
		input_text = json.dumps(payload)
	result = subprocess.run(
		command,
		input=input_text,
		text=True,
		capture_output=True,
		check=False,
	)
	if result.returncode:
		output = "\n".join(part for part in (result.stdout, result.stderr) if part)
		raise GitHubAPIError(result.returncode, output)
	return json.loads(result.stdout)


def protection_endpoint(repository: str, branch: str) -> str:
	return f"repos/{repository}/branches/{branch}/protection"


def main() -> int:
	root = Path(__file__).resolve().parents[1]
	parser = argparse.ArgumentParser(description="Apply or verify the repository branch-protection policy.")
	parser.add_argument(
		"--policy",
		type=Path,
		default=root / ".github" / "branch-protection.json",
	)
	parser.add_argument(
		"--apply",
		action="store_true",
		help="Apply the policy before verifying it.",
	)
	args = parser.parse_args()

	policy = load_policy(args.policy)
	endpoint = protection_endpoint(
		str(policy["repository"]),
		str(policy["default_branch"]),
	)
	try:
		if args.apply:
			run_gh_api(endpoint, method="PUT", payload=policy["protection"])
		actual = run_gh_api(endpoint)
	except GitHubAPIError as exc:
		if is_plan_blocker(exc.output):
			print(
				json.dumps(
					{
						"status": "blocked",
						"repository": policy["repository"],
						"branch": policy["default_branch"],
						"reason": "GitHub plan does not allow protection on this private repository",
					}
				),
				file=sys.stderr,
			)
			return PLAN_BLOCKED_EXIT
		print(str(exc), file=sys.stderr)
		return exc.returncode or 1

	mismatches = compare_protection(policy["protection"], actual)
	if mismatches:
		print("BRANCH PROTECTION MISMATCH", file=sys.stderr)
		for mismatch in mismatches:
			print(f"- {mismatch}", file=sys.stderr)
		return 1

	print(
		json.dumps(
			{
				"status": "ok",
				"repository": policy["repository"],
				"branch": policy["default_branch"],
				"applied": args.apply,
			}
		)
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
