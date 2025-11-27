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

