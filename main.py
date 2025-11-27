import logging as log
import os
import sys
from gh import clone_gitlab_repo, ensure_github_repo_exists, push_to_github

GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITLAB_REPO = os.getenv('GITLAB_REPO')
GITHUB_REPO = os.getenv('GITHUB_REPO')
LOCAL_CLONE_DIR = "repo"

log.basicConfig(level=log.INFO, format='%(levelname)s: %(message)s')

if not GITLAB_TOKEN:
    log.error("GITLAB_TOKEN is not set. Please set environment value GITLAB_TOKEN")
    sys.exit(1)
if not GITHUB_TOKEN:
    log.error("GITHUB_TOKEN is not set. Please set environment value GITHUB_TOKEN")
    sys.exit(1)

if __name__ == "__main__":
    clone_gitlab_repo(LOCAL_CLONE_DIR, GITLAB_TOKEN, GITLAB_REPO)
    target_owner, target_repo = ensure_github_repo_exists(GITHUB_REPO)
    push_to_github(target_owner, target_repo, GITHUB_TOKEN, LOCAL_CLONE_DIR)
