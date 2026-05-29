"""
Tests for utils.py

Covers:
- inject_github_token() URL injection logic
- cleanup_temp_data() removes paths correctly
- create_pdf() returns valid bytes
"""

import os
import pytest
import tempfile

from utils import inject_github_token, cleanup_temp_data, create_pdf, TEMP_REPO_PATH, CHROMA_PATH


# ── inject_github_token ────────────────────────────────────────────────────────

class TestInjectGithubToken:

    def test_injects_token_into_https_url(self):
        url = "https://github.com/owner/repo.git"
        result = inject_github_token(url, "mytoken123")
        assert "mytoken123@github.com" in result

    def test_scheme_preserved(self):
        url = "https://github.com/owner/repo.git"
        result = inject_github_token(url, "tok")
        assert result.startswith("https://")

    def test_path_preserved(self):
        url = "https://github.com/owner/repo.git"
        result = inject_github_token(url, "tok")
        assert result.endswith("/owner/repo.git")

    def test_no_token_returns_original_url(self):
        url = "https://github.com/owner/repo.git"
        assert inject_github_token(url, "") == url
        assert inject_github_token(url, None) == url

    def test_token_not_doubled_on_already_authed_url(self):
        """If URL somehow already has a token, new token should replace it, not stack."""
        url = "https://oldtoken@github.com/owner/repo.git"
        result = inject_github_token(url, "newtoken")
        assert result.count("@") == 1
        assert "newtoken@github.com" in result
        assert "oldtoken" not in result

    def test_raises_on_non_https_url(self):
        with pytest.raises(ValueError, match="HTTPS"):
            inject_github_token("git@github.com:owner/repo.git", "token")

    def test_token_with_special_chars(self):
        """PATs are alphanumeric but test robustness."""
        url = "https://github.com/owner/repo.git"
        result = inject_github_token(url, "ghp_abc123XYZ")
        assert "ghp_abc123XYZ@github.com" in result


# ── cleanup_temp_data ──────────────────────────────────────────────────────────

class TestCleanupTempData:

    def test_removes_existing_directories(self, tmp_path, monkeypatch):
        """cleanup_temp_data should delete both TEMP_REPO_PATH and CHROMA_PATH."""
        fake_repo = tmp_path / "temp_repo_clone"
        fake_chroma = tmp_path / "chroma_db"
        fake_repo.mkdir()
        fake_chroma.mkdir()

        # Patch the constants so cleanup targets our temp dirs
        monkeypatch.setattr("utils.TEMP_REPO_PATH", str(fake_repo))
        monkeypatch.setattr("utils.CHROMA_PATH", str(fake_chroma))

        cleanup_temp_data()

        assert not fake_repo.exists()
        assert not fake_chroma.exists()

    def test_does_not_raise_if_paths_missing(self, monkeypatch, tmp_path):
        """Should be safe to call even if dirs don't exist."""
        monkeypatch.setattr("utils.TEMP_REPO_PATH", str(tmp_path / "nonexistent_repo"))
        monkeypatch.setattr("utils.CHROMA_PATH", str(tmp_path / "nonexistent_chroma"))
        cleanup_temp_data()  # Should not raise


# ── create_pdf ─────────────────────────────────────────────────────────────────

class TestCreatePdf:

    def _sample_messages(self):
        return [
            {"role": "user", "content": "Who introduced the timeout bug?"},
            {"role": "assistant", "content": "Commit abc123 by John Doe changed timeout from 5 to 10."},
        ]

    def test_returns_bytes(self):
        result = create_pdf("https://github.com/owner/repo", self._sample_messages())
        assert isinstance(result, bytes)

    def test_output_is_non_empty(self):
        result = create_pdf("https://github.com/owner/repo", self._sample_messages())
        assert len(result) > 0

    def test_pdf_starts_with_pdf_header(self):
        result = create_pdf("https://github.com/owner/repo", self._sample_messages())
        # All valid PDFs start with %PDF
        assert result[:4] == b"%PDF"

    def test_works_with_empty_messages(self):
        try:
            result = create_pdf("https://github.com/owner/repo", [])
            assert result is None or isinstance(result, bytes)
        except Exception as e:
            pytest.fail(f"create_pdf raised unexpectedly: {e}")

    def test_handles_unicode_gracefully(self):
        messages = [
            {"role": "user", "content": "What changed in 2023? — some unicode: café résumé"},
            {"role": "assistant", "content": "Here is the summary with special chars: ñ ü ö"},
        ]
        # Should not raise even with non-latin chars (they get replaced)
        result = create_pdf("https://github.com/owner/repo", messages)
        assert isinstance(result, bytes)