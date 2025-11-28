# GitLab to GitHub Migrator

## Features
- Clone a GitLab repository onto to GitHub repository
- Sync Merge Requests from GitLab to Pull Requests on GitHub

## Requirements
- Python 3.8+
- Set environment variables:
  - `GITLAB_TOKEN` — personal access token for GitLab (used for API and clone)
  - `GITHUB_TOKEN` — personal access token for GitHub (used for API and push)

## Install
```bash
pip install -r requirements.txt
```

## CLI overview
The tool uses subcommands to separate two modes of operation:

- clone — mirror a GitLab repository to GitHub
- sync  — copy Merge Requests to Pull Requests

Each mode has its own arguments and validation.

### Clone (mirror repository)
Required arguments:
- `--gitlab-repo GITLAB_REPO` (e.g. https://gitlab.com/group/project.git or group/project)
- `--github-repo GITHUB_REPO` (owner/repo)

Example:
```bash
python main.py clone --gitlab-repo group/project --github-repo owner/repo
```
This will clone the GitLab repo into a local `repo/` folder and then push it to the GitHub repository.

### Sync (Merge Requests → Pull Requests)
Required arguments:
- `--gitlab-repo GITLAB_REPO` (GitLab project to read MRs from)
- `--github-repo GITHUB_REPO` (target GitHub repository)
- Exactly one of:
  - `--mr-iid MR_IID` (sync a single MR by IID)
  - `--mr-all` (sync all open MRs)
Optional:
- `--dry-run` — don't create PRs on GitHub, just show what would be done

Examples:
```bash
# Sync one MR
python main.py sync --gitlab-repo group/project --github-repo owner/repo --mr-iid 123

# Sync all open MRs (dry-run)
python main.py sync --gitlab-repo group/project --github-repo owner/repo --mr-all --dry-run
```

## Notes
- Tokens are read from environment variables; do not pass tokens on the command line.
- When syncing a MR, the tool will check that the MR's source branch exists on GitHub; pushing a missing branch from a local clone is supported but is not enabled by default. Use the code flag `push_branch_if_missing` (or we can add a CLI flag) to enable automatic pushing.

## Troubleshooting
- Ensure `GITLAB_TOKEN` and `GITHUB_TOKEN` are set and have appropriate scopes (`repo` for GitHub; API scope for GitLab).
- If cloning fails, check network access and that the GitLab token is valid for clone operations.

## Contributing
PRs welcome — prefer small, focused changes and include tests where possible.
