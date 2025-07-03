# git_ops.py

import git
from github import Github
from git.exc import InvalidGitRepositoryError

def init_repo(repo_path="."):
    try:
        return git.Repo(repo_path)
    except InvalidGitRepositoryError:
        repo = git.Repo.init(repo_path)
        return repo

def get_status(repo):
    return repo.git.status()

def create_branch(repo, branch_name):
    if branch_name in repo.heads:
        branch = repo.heads[branch_name]
    else:
        branch = repo.create_head(branch_name)
    branch.checkout()
    return f"✅ Switched to branch: {branch_name}"

def commit_and_push(repo, branch_name, commit_message, remote_url=None, github_token=None):
    repo.git.add(A=True)
    repo.index.commit(commit_message)
    if remote_url:
        if not repo.remotes:
            repo.create_remote('origin', remote_url)
        repo.git.push('--set-upstream', 'origin', branch_name)
    else:
        repo.git.push('--set-upstream', 'origin', branch_name)
    return f"✅ Changes pushed to {branch_name}"

def create_pull_request(remote_url, github_token, branch_name, pr_title, pr_body=""):
    g = Github(github_token)
    parts = remote_url.replace(".git", "").split("/")
    owner, repo_name = parts[-2], parts[-1]
    repo = g.get_user(owner).get_repo(repo_name)
    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base="main"
    )
    return f"✅ Pull request created: {pr.html_url}"

