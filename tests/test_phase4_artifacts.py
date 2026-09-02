from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from delta.artifacts import ArtifactResolutionStatus, ArtifactSafetyError, ArtifactStore
from delta.core import ArtifactReference


class PhaseFourArtifactTests(unittest.TestCase):
    def test_generated_artifact_is_local_and_hash_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-artifacts-") as directory:
            store = ArtifactStore(directory)
            created = store.write_generated(b"generated visual", media_type="image/png")
            self.assertEqual(created.status, ArtifactResolutionStatus.AVAILABLE)
            self.assertIsNotNone(created.reference)
            resolved = store.resolve_local(created.reference)
            self.assertEqual(resolved.status, ArtifactResolutionStatus.AVAILABLE)

    def test_missing_and_traversal_artifacts_are_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-artifacts-") as directory:
            root = Path(directory)
            store = ArtifactStore(root)
            missing = ArtifactReference("artifact-missing", "sha256:missing", "text/plain", 4, (root / "artifact-missing.bin").as_uri(), True)
            self.assertEqual(store.resolve_local(missing).status, ArtifactResolutionStatus.UNAVAILABLE)
            traversal = ArtifactReference("artifact-escape", "sha256:escape", "text/plain", 6, (root / ".." / "artifact-escape.bin").as_uri(), True)
            self.assertEqual(store.resolve_local(traversal).status, ArtifactResolutionStatus.INVALID)

    def test_local_reference_requires_generated_file_uri(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-artifacts-") as directory:
            store = ArtifactStore(directory)
            reference = ArtifactReference("artifact-http", "sha256:http", "text/plain", 4, "http://example.invalid/artifact-http.bin", True)
            self.assertEqual(store.resolve_local(reference).status, ArtifactResolutionStatus.INVALID)

    def test_remote_resolution_allows_https_only_and_handles_timeout_and_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-artifacts-") as directory:
            store = ArtifactStore(directory)
            content = b"remote copy"
            expected = f"sha256:{sha256(content).hexdigest()}"
            resolved = store.resolve_remote(
                "https://provider.example/artifact",
                media_type="text/plain",
                expected_hash=expected,
                fetcher=lambda _url, _timeout, _limit: content,
            )
            self.assertEqual(resolved.status, ArtifactResolutionStatus.AVAILABLE)
            timed_out = store.resolve_remote(
                "https://provider.example/slow",
                media_type="text/plain",
                fetcher=lambda _url, _timeout, _limit: (_ for _ in ()).throw(TimeoutError()),
            )
            self.assertEqual(timed_out.status, ArtifactResolutionStatus.UNAVAILABLE)
            failed = store.resolve_remote(
                "https://provider.example/error",
                media_type="text/plain",
                fetcher=lambda _url, _timeout, _limit: (_ for _ in ()).throw(OSError("fixture failure")),
            )
            self.assertEqual(failed.status, ArtifactResolutionStatus.ERROR)
            with self.assertRaises(ArtifactSafetyError):
                store.resolve_remote("http://provider.example/artifact", media_type="text/plain")

    def test_hash_mismatch_is_invalid_and_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-artifacts-") as directory:
            store = ArtifactStore(directory)
            result = store.write_generated(b"actual bytes", media_type="application/octet-stream", expected_hash="sha256:wrong")
            self.assertEqual(result.status, ArtifactResolutionStatus.INVALID)
            self.assertIsNone(result.reference)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
