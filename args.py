import argparse


def build_args():
    parser = argparse.ArgumentParser(
        description="Migrate a GitLab repository to GitHub: clone from GitLab and push to GitHub.")

    parser.add_argument(
        "--gitlab-repo",
        dest="gitlab_repo",
        required=True,
        help="GitLab repository path or URL (e.g. group/project or https://gitlab.com/group/project.git)",
    )

    parser.add_argument(
        "--github-repo",
        dest="github_repo",
        required=True,
        help="Target GitHub repository in the format owner/repo (e.g. kanataidarov/myrepo)",
    )

    return parser
