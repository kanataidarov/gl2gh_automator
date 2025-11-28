from args import build_args

import gh
import gl
import logging as log
import os

GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def main():
    if not GITLAB_TOKEN:
        log.error("GITLAB_TOKEN is not set. Please set environment value GITLAB_TOKEN")
        return False
    if not GITHUB_TOKEN:
        log.error("GITHUB_TOKEN is not set. Please set environment value GITHUB_TOKEN")
        return False

    log.basicConfig(level=log.INFO, format='%(levelname)s: %(message)s')

    args = build_args().parse_args()

    if args.command == 'clone':
        gl.clone_repo(args.gitlab_repo)
        gh_owner, gh_repo = gh.ensure_repo(args.github_repo)
        gh.push_repo(gh_owner, gh_repo)
        return True

    if args.command == 'sync':
        gh_owner, gh_repo = gh.ensure_repo(args.github_repo)
        if args.mr_url:
            mr = gl.get_mr(args.gitlab_repo, args.mr_url)
            if not mr:
                log.error(f"Merge request {args.mr_url} not found.")
                return False

            branch = mr.get('source_branch')
            web_url = mr.get('web_url')
            created = gl.ensure_local_branch(branch, web_url)
            if not created:
                log.error(f"Failed to ensure local branch '{branch}' for MR '{args.mr_url}'")
                return False

            branch_ok = gh.push_branch_from_local(gh_owner, gh_repo, branch)
            if not branch_ok:
                log.error(f"Head branch '{branch}' is not available on GitHub for {gh_owner}/{gh_repo} and could not be pushed.")
                return False

            success = gh.sync_mr_to_pr(args.gitlab_repo, mr, gh_owner, gh_repo)
            if not success:
                log.error("Failed to sync MR to PR")
                return True
        elif args.mr_all:
            mrs = gl.list_mrs(args.gitlab_repo)
            failures = 0
            for mr in mrs:
                branch = mr.get('source_branch')
                web_url = mr.get('web_url')
                created = gl.ensure_local_branch(branch, web_url)
                if not created:
                    log.error(f"Failed to ensure local branch '{branch}' for MR '{args.mr_url}'")
                    failures += 1
                    continue

                branch_ok = gh.push_branch_from_local(gh_owner, gh_repo, branch)
                if not branch_ok:
                    log.error(
                        f"Head branch '{branch}' is not available on GitHub for {gh_owner}/{gh_repo} and could not be pushed.")
                    failures += 1
                    continue

                success = gh.sync_mr_to_pr(args.gitlab_repo, mr, gh_owner, gh_repo)
                if not success:
                    failures += 1
            if failures:
                log.error(f"Failed to sync {failures} merge requests")
                return False
        return True

    log.error("Unknown command or missing subcommand")
    return False


if __name__ == "__main__":
    main()