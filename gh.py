import json
import logging as log
import os
import subprocess
import sys
import urllib.request
import urllib.error


GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
LOCAL_CLONE_DIR = os.getenv('LOCAL_CLONE_DIR', 'repo')


def ensure_repo(gh_repo):
    owner, repo = _parse_owner_repo(gh_repo)
    log.info(f"Checking if GitHub repo '{owner}/{repo}' exists...")
    code, body = _api_request(f"/repos/{owner}/{repo}")
    if code == 200:
        log.info("GitHub repository exists.")
        return owner, repo

    auth_user = _authenticated_user()
    log.info(f"Authenticated GitHub user: {auth_user or '<unknown>'}")

    if code == 404:
        log.info("GitHub repository not found — attempting to create it.")
        create_payload = {"name": repo, "private": False}
        if auth_user is None or auth_user == owner:
            log.info(f"Attempting to create repository '{repo}' under user account '{auth_user or owner}'.")
            code_user, body_user = _api_request('/user/repos', method='POST', data=create_payload)
            if code_user in (201, 200):
                created_owner = auth_user if auth_user else owner
                log.info(f"Created repository '{created_owner}/{repo}' under authenticated user.")
                return created_owner, repo
            log.info(f"User repo creation returned status {code_user}. Response: {body_user}")
        log.info(f"Attempting to create repository under organization '{owner}'.")
        code_org, body_org = _api_request(f"/orgs/{owner}/repos", method='POST', data={"name": repo, "private": False})
        if code_org in (201, 200):
            log.info(f"Created repository '{owner}/{repo}' under organization '{owner}'.")
            return owner, repo

        if auth_user and auth_user != owner:
            log.info(f"Organization creation failed; attempting to create repository under authenticated user '{auth_user}' as a fallback.")
            code_user2, body_user2 = _api_request('/user/repos', method='POST', data=create_payload)
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


def push_repo(gh_owner, gh_repo):
    log.info(f"Pushing to GitHub repository '{gh_repo}' ...")
    if not os.path.isdir(LOCAL_CLONE_DIR):
        log.error(f"Repository directory '{LOCAL_CLONE_DIR}' does not exist. Cannot push to GitHub.")
        sys.exit(1)
    owner, repo = gh_owner, gh_repo
    os.chdir(LOCAL_CLONE_DIR)
    try:
        subprocess.run(["git", "remote", "remove", "origin"], check=True)
    except subprocess.CalledProcessError:
        log.info("No existing 'origin' remote to remove or removal failed; continuing.")
    remote_url = f"https://{GITHUB_TOKEN}@github.com/{owner}/{repo}.git"
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


def push_branch_from_local(owner, repo, branch):
    existed_before_push = False
    try:
        if _branch_exists(owner, repo, branch):
            log.info(f"Branch '{branch}' already exists on {owner}/{repo}.")
            existed_before_push = True
    except Exception as e:
        log.warning(f"Could not determine if branch '{branch}' exists before push: {e}")

    masked = f"https://***@github.com/{owner}/{repo}.git"
    log.info(f"Pushing local branch '{branch}' to remote {owner}/{repo} (remote URL masked: {masked})")
    remote_url = f"https://{GITHUB_TOKEN}@github.com/{owner}/{repo}.git"
    try:
        subprocess.run(["git", "-C", LOCAL_CLONE_DIR, "push", remote_url, f"{branch}:{branch}"], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to push branch '{branch}' to {owner}/{repo}: {e}")
        return False

    re_exists = _branch_exists(owner, repo, branch)
    if re_exists:
        if not existed_before_push:
            log.info(f"Successfully pushed branch '{branch}' to {owner}/{repo}.")
        return True

    log.error(f"Branch '{branch}' still not visible on GitHub after push attempt.")
    return False


def sync_mr_to_pr(gitlab_repo, mr, gh_owner, gh_repo):
    """Convert a GitLab MR (dict as returned by GitLab API) to a GitHub PR.
    mr: the MR dict from GitLab. gitlab_repo: original project identifier (path or url) for reference.
    user_map: optional dict mapping gitlab usernames to github logins.
    Returns True on success, False on failure.
    """
    title = mr.get('title')
    description = mr.get('description') or ''
    iid = mr.get('iid')
    source_branch = mr.get('source_branch')
    target_branch = mr.get('target_branch')
    author = mr.get('author', {}) or {}
    author_name = author.get('name') or author.get('username')
    web_url = mr.get('web_url')

    provenance = f"\n\n---\nImported from GitLab project {gitlab_repo} MR !{iid} by {author_name}. Original: {web_url}"
    body = (description or '') + provenance

    try:
        code_prs, prs = _api_request(f"/repos/{gh_owner}/{gh_repo}/pulls?state=open")
        if code_prs == 200 and isinstance(prs, list):
            for existing_pr in prs:
                if (existing_pr.get('title') or '').strip() == (title or '').strip():
                    log.info(f"Open PR with title `{title}` already exists: #{existing_pr.get('number')} - {existing_pr.get('html_url')}")
                    return True
    except Exception as e:
        log.warning(f"Failed to check existing PRs before creating PR: {e}")


    pr = _create_pull_request(gh_owner, gh_repo, source_branch, target_branch, title, body)
    if pr is None:
        log.error(f"Failed to create PR for MR !{iid}")
        return False

    log.info(f"Synchronized MR !{iid} -> PR on {gh_owner}/{gh_repo}")
    return True


def _parse_owner_repo(url):
    if url.startswith("https://"):
        path = url.split('https://github.com/')[1]
    else:
        path = url.split('github.com/')[-1]
    path = path.rstrip('/')
    if path.endswith('.git'):
        path = path[:-4]
    parts = path.split('/')
    if len(parts) >= 2:
        return parts[0], parts[1]
    raise ValueError(f"Cannot parse owner and repo from {url}")


def _api_request(path, method='GET', data=None, headers=None):
    """Make a request to the GitHub REST API and return (status_code, json_body-or-None)."""
    url = f"https://api.github.com{path}"
    req_headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'gl2gh-automator'
    }
    if headers:
        req_headers.update(headers)
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        req_headers['Content-Type'] = 'application/json'
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode('utf-8')
            return resp.getcode(), json.loads(resp_body) if resp_body else None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        return e.code, json.loads(err_body) if err_body else None
    except Exception as e:
        log.error(f"GitHub API request failed: {e}")
        return None, None


def _authenticated_user():
    """Return the login of the authenticated GitHub user, or None if it cannot be determined."""
    code, body = _api_request('/user')
    if code == 200 and body and 'login' in body:
        return body['login']
    log.warning(f"Couldn't determine authenticated GitHub user (status {code}). Proceeding without user-check.")
    return None


def _branch_exists(owner, repo, branch):
    """Return True if branch exists on GitHub, False otherwise."""
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    code, body = _api_request(f"/repos/{owner}/{repo}/branches/{branch}", headers=headers)
    if code == 200:
        log.info(f"Branch '{branch}' exists on {owner}/{repo}.")
        return True
    if code == 404:
        log.info(f"Branch '{branch}' does not exist on GitHub for {owner}/{repo}.")
        return False

    log.warning(f"Unexpected response checking branch '{branch}' on {owner}/{repo}: status={code} body={body}")
    return False


def _create_pull_request(owner, repo, head, base, title, body):
    log.info(f"Creating pull request on {owner}/{repo}: {title} ({head} -> {base})")

    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base
    }
    code, resp = _api_request(f"/repos/{owner}/{repo}/pulls", method='POST', data=payload)
    if code in (200, 201):
        log.info(f"Created PR #{resp.get('number')} at {resp.get('html_url')}")
        return resp

    log.error(f"Failed to create PR: status={code} body={resp}")
    return None
