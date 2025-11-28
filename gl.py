import logging as log
import os
import shutil
import subprocess
import sys

from utils import gitlab_api_request, gitlab_parse_project_id


def clone_gl_repo(local_clone_dir, gitlab_token, gitlab_repo):
    log.info(f"Cloning GitLab repository into '{local_clone_dir}' folder ...")
    if os.path.exists(local_clone_dir):
        try:
            if os.path.isdir(local_clone_dir):
                shutil.rmtree(local_clone_dir)
            else:
                os.remove(local_clone_dir)
            log.info(f"Removed existing '{local_clone_dir}' folder")
        except Exception as e:
            log.error(f"Failed to remove existing '{local_clone_dir}' folder: {e}")
            sys.exit(1)
    try:
        subprocess.run(["git", "clone", f"https://oauth2:{gitlab_token}@{gitlab_repo.split('https://')[1]}", local_clone_dir], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"GitLab clone failed: {e}")
        sys.exit(1)


# --- Merge Request helpers ---

def get_merge_request(gitlab_repo, iid, gitlab_host=None):
    """Fetch a single Merge Request by project (url/path or id) and iid. Returns dict or None."""
    project_id = gitlab_parse_project_id(gitlab_repo)
    path = f"/projects/{project_id}/merge_requests/{iid}"
    code, body = gitlab_api_request(path, gitlab_host=gitlab_host)
    if code == 200:
        return body
    log.error(f"Failed to fetch Merge Request {iid} from GitLab project {gitlab_repo}: status={code} body={body}")
    return None


def list_merge_requests(gitlab_repo, state='opened', gitlab_host=None):
    """List merge requests for a project. Returns list of MR dicts (may be empty)."""
    project_id = gitlab_parse_project_id(gitlab_repo)
    path = f"/projects/{project_id}/merge_requests?state={state}&per_page=100"
    code, body = gitlab_api_request(path, gitlab_host=gitlab_host)
    if code == 200 and isinstance(body, list):
        return body
    log.error(f"Failed to list Merge Requests for project {gitlab_repo}: status={code} body={body}")
    return []


def get_merge_request_notes(gitlab_repo, iid, gitlab_host=None):
    project_id = gitlab_parse_project_id(gitlab_repo)
    path = f"/projects/{project_id}/merge_requests/{iid}/notes?per_page=100"
    code, body = gitlab_api_request(path, gitlab_host=gitlab_host)
    if code == 200 and isinstance(body, list):
        return body
    log.error(f"Failed to fetch notes for MR {iid} on project {gitlab_repo}: status={code} body={body}")
    return []
