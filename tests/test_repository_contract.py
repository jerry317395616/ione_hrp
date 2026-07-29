from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.repository_contract import (
    APP_NAME,
    collect_violations,
    discover_custom_apps,
    find_legacy_prefix_references,
    validate_branch_policy,
    validate_push_guard,
)

ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTest(unittest.TestCase):
    def test_current_repository_satisfies_contract(self) -> None:
        self.assertEqual(collect_violations(ROOT), [])

    def test_current_app_is_press_discoverable_from_repository_root(self) -> None:
        self.assertEqual(discover_custom_apps(ROOT)[APP_NAME], ROOT)
        self.assertTrue((ROOT / APP_NAME / "hooks.py").is_file())

    def test_discovers_multiple_custom_apps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in (APP_NAME, "ione_hrp_budget"):
                app_root = root / "apps" / name
                app_root.mkdir(parents=True)
                (app_root / "pyproject.toml").write_text(
                    f'[project]\nname = "{name}"\nversion = "1.0.0"\n',
                    encoding="utf-8",
                )
            self.assertEqual(set(discover_custom_apps(root)), {APP_NAME, "ione_hrp_budget"})

    def test_finds_legacy_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy_prefix = "myi" + "_hrp"
            (root / "README.md").write_text(f"legacy app: {legacy_prefix}", encoding="utf-8")
            self.assertEqual(
                find_legacy_prefix_references(root),
                [f"README.md contains {legacy_prefix}"],
            )

    def test_rejects_weakened_branch_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            policy_path = root / ".github" / "branch-protection.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text(
                json.dumps(
                    {
                        "default_branch": "main",
                        "protection": {
                            "required_status_checks": {
                                "strict": False,
                                "contexts": [],
                            },
                            "enforce_admins": False,
                            "required_pull_request_reviews": None,
                            "allow_force_pushes": True,
                            "allow_deletions": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            violations = validate_branch_policy(root)
            self.assertIn("pull requests must be required before merging", violations)
            self.assertIn("force pushes must be disabled", violations)

    def test_solo_maintainer_policy_still_requires_pull_requests(self) -> None:
        policy = json.loads(
            (ROOT / ".github" / "branch-protection.json").read_text(encoding="utf-8")
        )
        reviews = policy["protection"]["required_pull_request_reviews"]
        self.assertIsInstance(reviews, dict)
        self.assertEqual(reviews["required_approving_review_count"], 0)
        self.assertFalse(reviews["require_code_owner_reviews"])

    def test_rejects_missing_push_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(
                validate_push_guard(root),
                ["missing .githooks/pre-push"],
            )


if __name__ == "__main__":
    unittest.main()
