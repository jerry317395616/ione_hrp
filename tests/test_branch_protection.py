from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.apply_branch_protection import (
	compare_protection,
	is_plan_blocker,
	load_policy,
	protection_endpoint,
)


class BranchProtectionTest(unittest.TestCase):
	def test_normalizes_github_enabled_objects(self) -> None:
		expected = {
			"enforce_admins": True,
			"required_linear_history": True,
			"allow_force_pushes": False,
			"required_pull_request_reviews": {
				"required_approving_review_count": 1,
				"require_code_owner_reviews": True,
			},
		}
		actual = {
			"enforce_admins": {"enabled": True},
			"required_linear_history": {"enabled": True},
			"allow_force_pushes": {"enabled": False},
			"required_pull_request_reviews": {
				"required_approving_review_count": 1,
				"require_code_owner_reviews": True,
				"dismiss_stale_reviews": True,
			},
		}
		self.assertEqual(compare_protection(expected, actual), [])

	def test_reports_nested_mismatch(self) -> None:
		mismatches = compare_protection(
			{
				"required_pull_request_reviews": {
					"required_approving_review_count": 1,
				}
			},
			{
				"required_pull_request_reviews": {
					"required_approving_review_count": 0,
				}
			},
		)
		self.assertEqual(
			mismatches,
			["required_pull_request_reviews.required_approving_review_count: expected 1, got 0"],
		)

	def test_recognizes_private_repository_plan_blocker(self) -> None:
		self.assertTrue(
			is_plan_blocker("Upgrade to GitHub Pro or make this repository public to enable this feature.")
		)
		self.assertFalse(is_plan_blocker("Bad credentials"))

	def test_load_policy_requires_repository(self) -> None:
		with tempfile.TemporaryDirectory() as temp:
			path = Path(temp) / "policy.json"
			path.write_text(
				'{"default_branch":"main","protection":{}}',
				encoding="utf-8",
			)
			with self.assertRaisesRegex(ValueError, "repository"):
				load_policy(path)

	def test_builds_protection_endpoint(self) -> None:
		self.assertEqual(
			protection_endpoint("owner/repo", "main"),
			"repos/owner/repo/branches/main/protection",
		)


if __name__ == "__main__":
	unittest.main()
