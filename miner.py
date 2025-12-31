import git
from datetime import datetime
import os

IGNORE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.mp4', '.zip', '.tar', '.gz', '.lock', '.json'}
IGNORE_DIRS = {'dist', 'build', 'node_modules', '__pycache__', '.idea', '.vscode'}

def should_ignore(file_path):
    if not file_path: return True
    if any(file_path.endswith(ext) for ext in IGNORE_EXTENSIONS):
        return True
    if any(part in IGNORE_DIRS for part in file_path.split('/')):
        return True
    return False

def load_git_history(repo_path, branch="main", limit=None):
    """
    Generator function that yields commits one by one.
    """
    if not os.path.exists(repo_path):
        raise ValueError(f"Path not found: {repo_path}")

    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        raise ValueError(f"Not a valid git repo: {repo_path}")

    print(f"⛏️  Mining repository: {repo_path}...")

    target_branch = branch
    try:
        repo.git.rev_parse("--verify", branch)
    except:
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
                        
                        if len(patch_text) > 600:
                            patch_text = patch_text[:600] + "...\n(truncated)"
                            
                        diff_summary += f"\nFile: {file_path}\n{patch_text}\n"
                        
                    except Exception:
                        continue
            except git.exc.GitCommandError:
                diff_summary = "(Diff unavailable: Boundary of shallow clone)"
            except Exception:
                diff_summary = "(Diff failed to load)"
        else:
            diff_summary = "(First commit - no diffs)"

        if len(diff_summary) > 1500:
            diff_summary = diff_summary[:1500] + "...(Diff too long)"

        full_content = f"""
        Commit: {commit.hexsha}
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
            "content": full_content 
        }