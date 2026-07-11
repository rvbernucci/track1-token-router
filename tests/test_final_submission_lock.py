import unittest

from scripts.final_submission_lock import _digest


class FinalSubmissionLockTests(unittest.TestCase):
    def test_digest_requires_full_sha256(self) -> None:
        self.assertTrue(_digest("sha256:" + "a" * 64))
        self.assertFalse(_digest("sha256:" + "a" * 63))
        self.assertFalse(_digest("sha512:" + "a" * 64))


if __name__ == "__main__":
    unittest.main()
