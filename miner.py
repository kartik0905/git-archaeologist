import git
from datetime import datetime
import pandas as pd
import os

def load_git_history(repo_path, branch="main", limit=100):
    """
    Extracts commit history from a local git repository.
    
    Args:
        repo_path (str): Path to the local git repository.
        branch (str): The branch to analyze (usually 'main' or 'master').
        limit (int): How many recent commits to fetch (to keep it fast for testing).
    
    Returns:
        list: A list of dictionaries containing commit data.
    """
    
    if not os.path.exists(repo_path):
        raise ValueError(f"Path not found: {repo_path}")

    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        raise ValueError(f"Not a valid git repo: {repo_path}")

    print(f"⛏️  Mining repository: {repo_path} (Branch: {branch})")
    
    history_data = []


    try:
        commits = list(repo.iter_commits(branch, max_count=limit))
    except git.exc.GitCommandError:
        print(f"Branch '{branch}' not found, trying 'master'...")
        commits = list(repo.iter_commits("master", max_count=limit))

    for commit in commits:

        message = commit.message.strip()
        

        author = commit.author.name
        date = datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%d %H:%M:%S')
        

        stats = commit.stats.files
        changed_files = list(stats.keys())
        
        full_content = f"""
        Commit Hash: {commit.hexsha}
        Author: {author}
        Date: {date}
        Message: {message}
        Files Changed: {', '.join(changed_files)}
        """

        history_data.append({
            "hash": commit.hexsha,
            "author": author,
            "date": date,
            "message": message,
            "files": changed_files,
            "content": full_content 
        })

    print(f"Successfully extracted {len(history_data)} commits.")
    return history_data


if __name__ == "__main__":
    target_repo = "./sample_repo" 
    
    if not os.path.isdir(os.path.join(target_repo, ".git")):
        print("Current folder is not a git repo. Please change 'target_repo' to a valid path.")
    else:
        data = load_git_history(target_repo, limit=10)
        

        df = pd.DataFrame(data)
        print("\n--- PREVIEW OF EXTRACTED DATA ---")
        print(df[['author', 'date', 'message']].head())
        print("\n--- EXAMPLE CONTENT FOR LLM ---")
        print(data[0]['content'])