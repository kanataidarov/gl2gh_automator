from args import build_args
from gh import ensure_gh_repo_exists, push_to_gh, sync_merge_request_to_pr
from gl import clone_gl_repo, get_merge_request, list_merge_requests

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

    if args.command == 'clone':
        # clone subcommand: require gitlab_repo and github_repo
        clone_gl_repo(LOCAL_CLONE_DIR, GITLAB_TOKEN, args.gitlab_repo)
        target_owner, target_repo = ensure_gh_repo_exists(args.github_repo)
        push_to_gh(target_owner, target_repo, GITHUB_TOKEN, LOCAL_CLONE_DIR)
        sys.exit(0)

    if args.command == 'sync':
        # sync subcommand: require gitlab_repo, github_repo, and either mr_iid or mr_all
        target_owner, target_repo = ensure_gh_repo_exists(args.github_repo)
        if args.mr_iid:
            mr = get_merge_request(args.gitlab_repo, args.mr_iid)
            if not mr:
                log.error(f"Merge request {args.mr_iid} not found.")
                sys.exit(1)
            success = sync_merge_request_to_pr(args.gitlab_repo, mr, target_owner, target_repo, dry_run=args.dry_run, github_token=GITHUB_TOKEN, push_branch_if_missing=False, local_clone_dir=LOCAL_CLONE_DIR)
            if not success:
                log.error("Failed to sync MR to PR")
                sys.exit(1)
        elif args.mr_all:
            mrs = list_merge_requests(args.gitlab_repo, state='opened')
            failures = 0
            for mr in mrs:
                ok = sync_merge_request_to_pr(args.gitlab_repo, mr, target_owner, target_repo, dry_run=args.dry_run, github_token=GITHUB_TOKEN, push_branch_if_missing=False, local_clone_dir=LOCAL_CLONE_DIR)
                if not ok:
                    failures += 1
            if failures:
                log.error(f"Failed to sync {failures} merge requests")
                sys.exit(1)
        sys.exit(0)

    # argparse should prevent reaching here
    log.error("Unknown command or missing subcommand")
    sys.exit(1)
