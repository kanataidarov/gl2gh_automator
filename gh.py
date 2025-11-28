import logging as log
import os
import subprocess
import sys
from utils import parse_github_owner_repo, github_api_request, get_authenticated_user


def ensure_gh_repo_exists(github_repo):
    owner, repo = parse_github_owner_repo(github_repo)
    log.info(f"Checking if GitHub repo '{owner}/{repo}' exists...")
    code, body = github_api_request(f"/repos/{owner}/{repo}")
    if code == 200:
        log.info("GitHub repository exists.")
        return owner, repo

    auth_user = get_authenticated_user()
    log.info(f"Authenticated GitHub user: {auth_user or '<unknown>'}")

    if code == 404:
        log.info("GitHub repository not found — attempting to create it.")
        create_payload = {"name": repo, "private": False}
        if auth_user is None or auth_user == owner:
            log.info(f"Attempting to create repository '{repo}' under user account '{auth_user or owner}'.")
            code_user, body_user = github_api_request('/user/repos', method='POST', data=create_payload)
            if code_user in (201, 200):
                created_owner = auth_user if auth_user else owner
                log.info(f"Created repository '{created_owner}/{repo}' under authenticated user.")
                return created_owner, repo
            log.info(f"User repo creation returned status {code_user}. Response: {body_user}")
        log.info(f"Attempting to create repository under organization '{owner}'.")
        code_org, body_org = github_api_request(f"/orgs/{owner}/repos", method='POST', data={"name": repo, "private": False})
        if code_org in (201, 200):
            log.info(f"Created repository '{owner}/{repo}' under organization '{owner}'.")
            return owner, repo

        if auth_user and auth_user != owner:
            log.info(f"Organization creation failed; attempting to create repository under authenticated user '{auth_user}' as a fallback.")
            code_user2, body_user2 = github_api_request('/user/repos', method='POST', data=create_payload)
            if code_user2 in (201, 200):
                log.info(f"Created repository '{auth_user}/{repo}' under authenticated user as a fallback.")
                return auth_user, repo
            log.info(f"Fallback user repo creation returned status {code_user2}. Response: {body_user2}")

        log.error("Failed to create GitHub repository. Possible reasons:\n"
                      " - The provided GITHUB_TOKEN doesn't have the 'repo' scope to create repositories.\n"
                      " - You're attempting to create a repo under an organization and the token lacks 'admin:org' permissions.\n"
                      " - The authenticated user is different from the target owner and doesn't have permission to create repos in that owner.\n"
                      f"API responses: user_create={locals().get('code_user')}, org_create={locals().get('code_org')}. Details: {locals().get('body_user') or locals().get('body_org')}")
        log.error("Ensure your GITHUB_TOKEN is a Personal Access Token with the 'repo' scope, and 'admin:org' if creating inside an org. You can also pre-create the repository manually and re-run.")
        sys.exit(1)

    else:
        log.error(f"Unexpected response checking repository: status {code}, body: {body}")
        sys.exit(1)


def push_to_gh(target_owner, target_repo, github_token, local_clone_dir="repo"):
    log.info(f"Pushing to GitHub repository '{target_repo}' ...")
    if not os.path.isdir(local_clone_dir):
        log.error(f"Repository directory '{local_clone_dir}' does not exist. Cannot push to GitHub.")
        sys.exit(1)
    owner, repo = target_owner, target_repo
    os.chdir(local_clone_dir)
    try:
        subprocess.run(["git", "remote", "remove", "origin"], check=True)
    except subprocess.CalledProcessError:
        log.info("No existing 'origin' remote to remove or removal failed; continuing.")
    remote_url = f"https://{github_token}@github.com/{owner}/{repo}.git"
    try:
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to add remote 'origin': {e}")
        sys.exit(1)
    try:
        subprocess.run(["git", "push", "--mirror", "origin"], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to push to GitHub: {e}")
        sys.exit(1)


# --- New: branch helpers ---

def gh_branch_exists(owner, repo, branch, github_token=None):
    """Return True if branch exists on GitHub, False otherwise.
    If github_token is provided, it will be used for the API call (safer for per-call tokens).
    """
    headers = None
    if github_token:
        headers = {'Authorization': f'token {github_token}'}
    code, body = github_api_request(f"/repos/{owner}/{repo}/branches/{branch}", headers=headers)
    if code == 200:
        log.info(f"Branch '{branch}' exists on {owner}/{repo}.")
        return True
    if code == 404:
        log.info(f"Branch '{branch}' not found on {owner}/{repo}.")
        return False
    # Unexpected response
    log.warning(f"Unexpected response checking branch '{branch}' on {owner}/{repo}: status={code} body={body}")
    return False


def ensure_branch_present_or_push(owner, repo, branch, github_token=None, push_if_missing=False, local_clone_dir="repo"):
    """Ensure 'branch' exists on GitHub for owner/repo. If missing and push_if_missing is True,
    attempt to push it from the local clone at local_clone_dir using github_token.
    Returns True if branch exists (or was pushed successfully), False otherwise.
    """
    # First check remotely
    exists = gh_branch_exists(owner, repo, branch, github_token=github_token)
    if exists:
        return True

    log.info(f"Branch '{branch}' does not exist on GitHub for {owner}/{repo}.")
    if not push_if_missing:
        log.info("Not configured to push missing branches. Skipping push.")
        return False

    # Need to push from local clone
    if not os.path.isdir(local_clone_dir):
        log.error(f"Local clone directory '{local_clone_dir}' not found; cannot push branch '{branch}'.")
        return False

    # Verify local branch exists
    try:
        res = subprocess.run(["git", "-C", local_clone_dir, "rev-parse", "--verify", f"refs/heads/{branch}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            log.error(f"Local branch '{branch}' not found in '{local_clone_dir}'; cannot push to GitHub.")
            return False
    except Exception as e:
        log.error(f"Failed to verify local branch '{branch}': {e}")
        return False

    # Push the branch to GitHub using a direct push (avoid adding a persistent remote). Do not log the token.
    masked = f"https://***@github.com/{owner}/{repo}.git"
    log.info(f"Pushing local branch '{branch}' to remote {owner}/{repo} (remote URL masked: {masked})")
    if not github_token:
        log.error("No github_token provided for pushing branch. Set GITHUB_TOKEN env or pass github_token.")
        return False
    remote_url = f"https://{github_token}@github.com/{owner}/{repo}.git"
    try:
        subprocess.run(["git", "-C", local_clone_dir, "push", remote_url, f"{branch}:{branch}"], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to push branch '{branch}' to {owner}/{repo}: {e}")
        return False

    # Re-check
    re_exists = gh_branch_exists(owner, repo, branch, github_token=github_token)
    if re_exists:
        log.info(f"Successfully pushed branch '{branch}' to {owner}/{repo}.")
        return True
    log.error(f"Branch '{branch}' still not visible on GitHub after push attempt.")
    return False


def create_pull_request(owner, repo, head, base, title, body, dry_run=False):
    log.info(f"Creating pull request on {owner}/{repo}: {title} ({head} -> {base})")
    if dry_run:
        log.info("Dry-run enabled: not creating PR on GitHub")
        return None
    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base
    }
    code, resp = github_api_request(f"/repos/{owner}/{repo}/pulls", method='POST', data=payload)
    if code in (200, 201):
        log.info(f"Created PR #{resp.get('number')} at {resp.get('html_url')}")
        return resp
    log.error(f"Failed to create PR: status={code} body={resp}")
    return None


def sync_merge_request_to_pr(gitlab_repo, mr, target_owner, target_repo, dry_run=False, github_token=None, push_branch_if_missing=False, local_clone_dir="repo"):
    """Convert a GitLab MR (dict as returned by GitLab API) to a GitHub PR.
    mr: the MR dict from GitLab. gitlab_repo: original project identifier (path or url) for reference.
    user_map: optional dict mapping gitlab usernames to github logins.
    Returns True on success, False on failure.
    """
    title = mr.get('title') or f"MR {mr.get('iid')}"
    description = mr.get('description') or ''
    iid = mr.get('iid')
    source_branch = mr.get('source_branch')
    target_branch = mr.get('target_branch')
    author = mr.get('author', {}) or {}
    author_name = author.get('name') or author.get('username')
    web_url = mr.get('web_url')

    provenance = f"\n\n---\nImported from GitLab project {gitlab_repo} MR !{iid} by {author_name}. Original: {web_url}"
    body = (description or '') + provenance

    head = source_branch

    # Ensure the head branch exists on GitHub or try to push it from the local clone if configured
    branch_ok = ensure_branch_present_or_push(target_owner, target_repo, head, github_token=github_token, push_if_missing=push_branch_if_missing, local_clone_dir=local_clone_dir)
    if not branch_ok:
        log.error(f"Head branch '{head}' is not available on GitHub for {target_owner}/{target_repo} and could not be pushed.")
        # If dry_run is enabled we allow continuing to call create_pull_request in dry-run mode (which won't create anything),
        # but if not dry_run this is a fatal error because PR creation will fail.
        if not dry_run:
            return False

    pr = create_pull_request(target_owner, target_repo, head, target_branch, title, body, dry_run=dry_run)
    if pr is None and not dry_run:
        log.error(f"Failed to create PR for MR !{iid}")
        return False

    log.info(f"Synchronized MR !{iid} -> PR on {target_owner}/{target_repo}")
    return True

