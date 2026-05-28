import git
from datetime import datetime
import os

IGNORE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.mp4', '.zip', '.tar', '.gz', '.lock', '.json'}
IGNORE_DIRS = {'dist', 'build', 'node_modules', '__pycache__', '.idea', '.vscode'}


def should_ignore(file_path: str) -> bool:
    if not file_path:
        return True
    if any(file_path.endswith(ext) for ext in IGNORE_EXTENSIONS):
        return True
    if any(part in IGNORE_DIRS for part in file_path.split('/')):
        return True
    return False


def load_git_history(repo_path: str, branch: str = "main", limit=None):
    """
    Generator that yields one commit dict at a time.
    Diffs are chunked by hunk (@@) rather than hard-truncated,
    giving the LLM cleaner, more meaningful context.
    """
    if not os.path.exists(repo_path):
        raise ValueError(f"Path not found: {repo_path}")

    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        raise ValueError(f"Not a valid git repo: {repo_path}")

    print(f"⛏️  Mining repository: {repo_path}...")

    # Fall back to master if main doesn't exist
    target_branch = branch
    try:
        repo.git.rev_parse("--verify", branch)
    except Exception:
        target_branch = "master"

    commits = repo.iter_commits(target_branch, max_count=limit)

    for commit in commits:
        message = commit.message.strip()
        author = commit.author.name
        date = datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%d %H:%M:%S')
        diff_summary = ""

        if commit.parents:
            try:
                parent = commit.parents[0]
                diffs = parent.diff(commit, create_patch=True)

                for diff in diffs:
                    try:
                        file_path = diff.b_path if diff.b_path else diff.a_path
                        if should_ignore(file_path):
                            continue

                        patch_text = diff.diff.decode('utf-8', errors='replace')

                        # Chunk by hunk (@@) instead of hard char truncation
                        hunks = patch_text.split('\n@@')
                        meaningful_hunks = []
                        total_len = 0

                        for i, hunk in enumerate(hunks):
                            hunk_text = hunk if i == 0 else '@@' + hunk
                            if total_len + len(hunk_text) > 1200:
                                meaningful_hunks.append("...(remaining hunks truncated)")
                                break
                            meaningful_hunks.append(hunk_text)
                            total_len += len(hunk_text)

                        diff_summary += f"\nFile: {file_path}\n{''.join(meaningful_hunks)}\n"

                    except Exception:
                        continue

            except git.exc.GitCommandError:
                diff_summary = "(Diff unavailable: boundary of shallow clone)"
            except Exception:
                diff_summary = "(Diff failed to load)"
        else:
            diff_summary = "(First commit — no parent diffs)"

        full_content = f"""Commit: {commit.hexsha}
Author: {author}
Date: {date}
Message: {message}

--- CODE CHANGES ---
{diff_summary}
"""

        yield {
            "hash": commit.hexsha,
            "author": author,
            "date": date,
            "message": message,
            "diff": diff_summary,
            "content": full_content,
        }