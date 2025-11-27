from args import build_args
from gh import clone_gl_repo, ensure_gh_repo_exists, push_to_gh

import logging as log
import os
import sys

GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

if not GITLAB_TOKEN:
    log.error("GITLAB_TOKEN is not set. Please set environment value GITLAB_TOKEN")
    sys.exit(1)
if not GITHUB_TOKEN:
    log.error("GITHUB_TOKEN is not set. Please set environment value GITHUB_TOKEN")
    sys.exit(1)

log.basicConfig(level=log.INFO, format='%(levelname)s: %(message)s')

LOCAL_CLONE_DIR = "repo"

if __name__ == "__main__":
    parser = build_args()
    args = parser.parse_args()

    clone_gl_repo(LOCAL_CLONE_DIR, GITLAB_TOKEN, args.gitlab_repo)
    target_owner, target_repo = ensure_gh_repo_exists(args.github_repo)
    push_to_gh(target_owner, target_repo, GITHUB_TOKEN, LOCAL_CLONE_DIR)
