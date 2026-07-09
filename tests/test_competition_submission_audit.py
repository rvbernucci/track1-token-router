import subprocess
import sys
import unittest
from pathlib import Path

from scripts.competition_submission_audit import (
    IMAGE_SIZE_LIMIT_BYTES,
    _validate_traceability,
    inspect_image_config,
    inspect_image_manifest,
    inspect_manifest_index,
    parse_image_ref,
    run_audit,
)


class CompetitionSubmissionAuditTests(unittest.TestCase):
    def test_parse_ghcr_image_ref_with_tag(self) -> None:
        image = parse_image_ref("ghcr.io/rvbernucci/track1-token-router:offline-rc-1")

        self.assertEqual(image.registry, "ghcr.io")
        self.assertEqual(image.repository, "rvbernucci/track1-token-router")
        self.assertEqual(image.reference, "offline-rc-1")

    def test_parse_ghcr_image_ref_requires_tag_or_digest(self) -> None:
        with self.assertRaises(ValueError):
            parse_image_ref("ghcr.io/rvbernucci/track1-token-router")

    def test_inspect_manifest_index_finds_linux_amd64(self) -> None:
        result = inspect_manifest_index(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": [
                    {
                        "digest": "sha256:attestation",
                        "size": 123,
                        "platform": {"os": "unknown", "architecture": "unknown"},
                    },
                    {
                        "digest": "sha256:amd64",
                        "size": 456,
                        "platform": {"os": "linux", "architecture": "amd64"},
                    },
                ],
            }
        )

        self.assertTrue(result["linux_amd64"])
        self.assertEqual(result["digest"], "sha256:amd64")

    def test_inspect_manifest_index_reports_missing_linux_amd64(self) -> None:
        result = inspect_manifest_index(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": [
                    {
                        "digest": "sha256:arm64",
                        "size": 456,
                        "platform": {"os": "linux", "architecture": "arm64"},
                    },
                ],
            }
        )

        self.assertFalse(result["linux_amd64"])

    def test_inspect_image_manifest_sums_compressed_layer_sizes(self) -> None:
        result = inspect_image_manifest(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": "sha256:config", "size": 100},
                "layers": [{"size": 200}, {"size": 300}],
            }
        )

        self.assertEqual(result["compressed_size_bytes"], 600)
        self.assertEqual(result["config_digest"], "sha256:config")
        self.assertTrue(result["under_10gb"])

    def test_inspect_image_manifest_detects_10gb_limit(self) -> None:
        result = inspect_image_manifest(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "layers": [{"size": IMAGE_SIZE_LIMIT_BYTES + 1}],
            }
        )

        self.assertFalse(result["under_10gb"])

    def test_inspect_image_config_extracts_oci_traceability_labels(self) -> None:
        result = inspect_image_config(
            {
                "config": {
                    "Labels": {
                        "org.opencontainers.image.source": "https://github.com/owner/repo",
                        "org.opencontainers.image.revision": "abc123",
                        "org.opencontainers.image.version": "offline-rc-1",
                    }
                }
            }
        )

        self.assertEqual(result["source"], "https://github.com/owner/repo")
        self.assertEqual(result["revision"], "abc123")
        self.assertEqual(result["version"], "offline-rc-1")

    def test_traceability_validation_fails_on_expected_label_mismatch(self) -> None:
        result = _validate_traceability(
            {"revision": "abc123", "version": "offline-rc-1", "source": "https://github.com/owner/repo"},
            expected_revision="other",
            expected_version="offline-rc-2",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], ["revision_mismatch", "version_mismatch"])

    def test_repository_fast_audit_passes_without_network_or_gates(self) -> None:
        report = run_audit(Path("."), skip_network=True, run_gates=False)

        self.assertTrue(report.ok, report.to_dict())

    def test_cli_fast_audit_writes_report(self) -> None:
        output = Path("reports/generated/test-competition-submission-audit.md")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/competition_submission_audit.py",
                "--skip-network",
                "--skip-gates",
                "--report",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn('"ok": true', result.stdout)
        self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
