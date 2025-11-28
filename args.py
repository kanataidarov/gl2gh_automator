import argparse


def build_args():
    parser = argparse.ArgumentParser(
        description="Migrate between GitLab and GitHub: use 'clone' to mirror a repo or 'sync' to copy Merge Requests to Pull Requests.")

    subparsers = parser.add_subparsers(dest='command', required=True, help='Operation to perform')

    clone_p = subparsers.add_parser('clone', help='Clone a GitLab repository and push it to GitHub')
    clone_p.add_argument(
        "--gitlab-repo",
        dest="gitlab_repo",
        required=True,
        help="GitLab repository path or URL (e.g. group/project or https://gitlab.com/group/project.git)",
    )
    clone_p.add_argument(
        "--github-repo",
        dest="github_repo",
        required=True,
        help="Target GitHub repository in the format owner/repo (e.g. kanataidarov/myrepo)",
    )

    sync_p = subparsers.add_parser('sync', help='Sync Merge Requests from GitLab to GitHub Pull Requests')
    sync_p.add_argument(
        "--gitlab-repo",
        dest="gitlab_repo",
        required=True,
        help="GitLab repository path or URL for MR source (e.g. group/project or https://gitlab.com/group/project.git)",
    )
    sync_p.add_argument(
        "--github-repo",
        dest="github_repo",
        required=True,
        help="Target GitHub repository in the format owner/repo (e.g. kanataidarov/myrepo)",
    )
    mr_group = sync_p.add_mutually_exclusive_group(required=True)
    mr_group.add_argument(
        "--mr-url",
        dest="mr_url",
        help="Merge Request URL to sync. Use with 'sync' to copy a single MR.",
    )
    mr_group.add_argument(
        "--mr-all",
        dest="mr_all",
        action='store_true',
        help="When used with 'sync', sync all open Merge Requests for the project.",
    )

    return parser
