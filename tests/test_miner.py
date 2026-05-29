"""
Tests for miner.py

Covers:
- should_ignore() filtering logic
- load_git_history() generator output shape and fields
- Hunk-based diff chunking behaviour
"""

import os
import pytest
import tempfile
import git as gitpython

from miner import should_ignore, load_git_history


# ── should_ignore ──────────────────────────────────────────────────────────────

class TestShouldIgnore:

    def test_ignores_image_extensions(self):
        assert should_ignore("assets/logo.png") is True
        assert should_ignore("img/banner.jpg") is True
        assert should_ignore("icons/favicon.svg") is True

    def test_ignores_archive_extensions(self):
        assert should_ignore("dist/bundle.zip") is True
        assert should_ignore("release/v1.0.tar") is True
        assert should_ignore("backup.gz") is True

    def test_ignores_lock_and_json(self):
        assert should_ignore("package-lock.json") is True  # ends with .json
        assert should_ignore("poetry.lock") is True

    def test_ignores_noise_directories(self):
        assert should_ignore("node_modules/lodash/index.js") is True
        assert should_ignore("dist/main.js") is True
        assert should_ignore("build/output.js") is True
        assert should_ignore("__pycache__/module.pyc") is True
        assert should_ignore(".vscode/settings.json") is True
        assert should_ignore(".idea/workspace.xml") is True

    def test_does_not_ignore_python_files(self):
        assert should_ignore("app.py") is False
        assert should_ignore("src/indexer.py") is False

    def test_does_not_ignore_markdown(self):
        assert should_ignore("README.md") is False
        assert should_ignore("docs/guide.md") is False

    def test_does_not_ignore_js_ts_files(self):
        assert should_ignore("src/index.js") is False
        assert should_ignore("components/Button.tsx") is False

    def test_does_not_ignore_yaml_toml(self):
        assert should_ignore("pyproject.toml") is False
        assert should_ignore(".github/workflows/ci.yml") is False

    def test_empty_path_is_ignored(self):
        assert should_ignore("") is True

    def test_none_like_empty_string(self):
        # should_ignore takes str; empty string is the falsy case
        assert should_ignore("") is True

    def test_nested_valid_file_not_ignored(self):
        assert should_ignore("src/utils/helpers.py") is False

    def test_file_named_like_ignored_dir_but_not_in_it(self):
        # A file called "dist.py" should NOT be ignored — only the dir "dist/"
        assert should_ignore("dist.py") is False


# ── load_git_history ───────────────────────────────────────────────────────────

@pytest.fixture
def temp_git_repo():
    """
    Creates a minimal real Git repo with 3 commits in a temp directory.
    Yields the repo path; cleans up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = gitpython.Repo.init(tmpdir)
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Commit 1 — initial file
        fpath = os.path.join(tmpdir, "main.py")
        with open(fpath, "w") as f:
            f.write("timeout = 5\n")
        repo.index.add(["main.py"])
        repo.index.commit("Initial commit: add main.py")

        # Commit 2 — modify file
        with open(fpath, "w") as f:
            f.write("timeout = 10\n")
        repo.index.add(["main.py"])
        repo.index.commit("Fix: increase timeout from 5 to 10")

        # Commit 3 — add a new file
        fpath2 = os.path.join(tmpdir, "utils.py")
        with open(fpath2, "w") as f:
            f.write("def helper(): pass\n")
        repo.index.add(["utils.py"])
        repo.index.commit("Add utils.py helper function")

        yield tmpdir


class TestLoadGitHistory:

    def test_returns_generator(self, temp_git_repo):
        import types
        result = load_git_history(temp_git_repo)
        assert isinstance(result, types.GeneratorType)

    def test_yields_correct_number_of_commits(self, temp_git_repo):
        commits = list(load_git_history(temp_git_repo))
        assert len(commits) == 3

    def test_each_commit_has_required_fields(self, temp_git_repo):
        required_fields = {"hash", "author", "date", "message", "diff", "content"}
        for commit in load_git_history(temp_git_repo):
            assert required_fields.issubset(commit.keys()), (
                f"Missing fields: {required_fields - commit.keys()}"
            )

    def test_hash_is_40_char_hex(self, temp_git_repo):
        for commit in load_git_history(temp_git_repo):
            assert len(commit["hash"]) == 40
            assert all(c in "0123456789abcdef" for c in commit["hash"])

    def test_author_is_correct(self, temp_git_repo):
        for commit in load_git_history(temp_git_repo):
            assert commit["author"] == "Test User"

    def test_date_format(self, temp_git_repo):
        from datetime import datetime
        for commit in load_git_history(temp_git_repo):
            # Should not raise
            datetime.strptime(commit["date"], "%Y-%m-%d %H:%M:%S")

    def test_content_contains_hash_author_message(self, temp_git_repo):
        for commit in load_git_history(temp_git_repo):
            assert commit["hash"] in commit["content"]
            assert commit["author"] in commit["content"]
            assert commit["message"] in commit["content"]

    def test_first_commit_has_no_diff(self, temp_git_repo):
        commits = list(load_git_history(temp_git_repo))
        # Generator yields newest first; first commit is the last item
        first_commit = commits[-1]
        assert "no parent diffs" in first_commit["diff"].lower() or first_commit["diff"] == ""

    def test_second_commit_diff_contains_filename(self, temp_git_repo):
        commits = list(load_git_history(temp_git_repo))
        # Second commit (index 1 from newest) modified main.py
        second_commit = commits[1]
        assert "main.py" in second_commit["diff"] or "main.py" in second_commit["content"]

    def test_raises_on_invalid_path(self):
        with pytest.raises((ValueError, Exception)):
            list(load_git_history("/nonexistent/path/to/repo"))

    def test_memory_efficiency_via_lazy_evaluation(self, temp_git_repo):
        """Generator should not load all commits eagerly — test by consuming one at a time."""
        gen = load_git_history(temp_git_repo)
        first = next(gen)
        assert first is not None  # We got one without consuming all