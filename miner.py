import git
from datetime import datetime
import os

def load_git_history(repo_path, branch="main", limit=50):
    if not os.path.exists(repo_path):
        raise ValueError(f"Path not found: {repo_path}")

    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        raise ValueError(f"Not a valid git repo: {repo_path}")

    print(f"⛏️  Mining repository: {repo_path}...")
    
    history_data = []

    try:
        commits = list(repo.iter_commits(branch, max_count=limit))
    except git.exc.GitCommandError:
        commits = list(repo.iter_commits("master", max_count=limit))

    for commit in commits:
        message = commit.message.strip()
        author = commit.author.name
        date = datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%d %H:%M:%S')
        
        diff_summary = ""
        
        if commit.parents:
            parent = commit.parents[0]
            diffs = parent.diff(commit, create_patch=True)
            
            for diff in diffs:
                try:
                    file_path = diff.b_path if diff.b_path else diff.a_path
                    
                    if "lock" in file_path or ".png" in file_path:
                        continue
                        
                    patch_text = diff.diff.decode('utf-8', errors='replace')
                    
                    if len(patch_text) > 800:
                        patch_text = patch_text[:800] + "...\n(truncated)"
                        
                    diff_summary += f"\nFile: {file_path}\n{patch_text}\n"
                    
                except Exception:
                    continue
        else:
            diff_summary = "(First commit - no diffs)"

        if len(diff_summary) > 2000:
            diff_summary = diff_summary[:2000] + "...(Diff too long)"

        full_content = f"""
        Commit: {commit.hexsha}
        Author: {author}
        Date: {date}
        Message: {message}
        
        --- CODE CHANGES ---
        {diff_summary}
        """

        history_data.append({
            "hash": commit.hexsha,
            "author": author,
            "date": date,
            "message": message,
            "diff": diff_summary,
            "files": list(commit.stats.files.keys()),
            "content": full_content 
        })

    return history_data