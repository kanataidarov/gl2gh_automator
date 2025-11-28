import json
import logging as log
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse


GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
LOCAL_CLONE_DIR = os.getenv('LOCAL_CLONE_DIR', 'repo')


def clone_gl_repo(gl_repo):
    log.info(f"Cloning GitLab repository into '{LOCAL_CLONE_DIR}' folder ...")
    if os.path.exists(LOCAL_CLONE_DIR):
        try:
            if os.path.isdir(LOCAL_CLONE_DIR):
                shutil.rmtree(LOCAL_CLONE_DIR)
            else:
                os.remove(LOCAL_CLONE_DIR)
            log.info(f"Removed existing '{LOCAL_CLONE_DIR}' folder")
        except Exception as e:
            log.error(f"Failed to remove existing '{LOCAL_CLONE_DIR}' folder: {e}")
            sys.exit(1)
    try:
        subprocess.run(["git", "clone", f"https://oauth2:{GITLAB_TOKEN}@{gl_repo.split('https://')[1]}", LOCAL_CLONE_DIR], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f"GitLab clone failed: {e}")
        sys.exit(1)


def get_mr(gl_repo, mr_url):
    """Fetch a single Merge Request by project (url/path or id) and MR URL. Returns dict or None."""
    project_id = _parse_pid(gl_repo)
    gl_host = _parse_host(gl_repo)
    iid = _parse_iid(mr_url)
    if not iid:
        log.error(f"Failed to parse IID from MR URL `{mr_url}`")
        return None
    path = f"/projects/{project_id}/merge_requests/{iid}"
    code, body = _api_request(path, gl_host)
    if code == 200:
        return body
    log.error(f"Failed to fetch Merge Request `{mr_url}` from GitLab project {gl_repo}: status={code} body={body}")
    return None


def list_mrs(gl_repo, state='opened'):
    """List merge requests for a project. Returns list of MR dicts (may be empty)."""
    project_id = _parse_pid(gl_repo)
    gl_host = _parse_host(gl_repo)
    path = f"/projects/{project_id}/merge_requests?state={state}&per_page=99"
    code, body = _api_request(path, gl_host)
    if code == 200 and isinstance(body, list):
        return body
    log.error(f"Failed to list Merge Requests for project {gl_repo}: status={code} body={body}")
    return []


def _api_request(path, gl_host, method='GET', data=None, headers=None):
    """Make a request to the GitLab REST API and return (status_code, json_body-or-None).
    path should start with '/'. Example: '/projects/:id/merge_requests'.
    """
    url = f"{gl_host}/api/v4{path}"
    req_headers = {
        'User-Agent': 'gl2gh-automator',
        'Accept': 'application/json'
    }
    if GITLAB_TOKEN:
        req_headers['Authorization'] = f'Bearer {GITLAB_TOKEN}'
    else:
        pass
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
        log.error(f"GitLab API request failed: {e}")
        return None, None


def _parse_pid(gl_repo):
    """Accepts either a URL (https://gitlab.com/group/project(.git)) or a path like group/project
    Returns URL-encoded project path suitable for /projects/:id endpoints (e.g. 'group%2Fproject')
    If gl_repo looks numeric, returns it unchanged.
    """
    repo = gl_repo
    if repo.startswith('https://'):
        if 'gitlab.com/' in repo:
            repo = repo.split('gitlab.com/')[-1]
        else:
            repo = repo.split('://', 1)[-1].split('/', 1)[-1]
    repo = repo.rstrip('/')
    if repo.endswith('.git'):
        repo = repo[:-4]
    if repo.isdigit():
        return repo
    return repo.replace('/', '%2F')


def _parse_host(gl_repo):
    """Extract scheme+host from a repo identifier."""
    repo = (gl_repo or '').strip()
    if not repo:
        return 'https://gitlab.com'

    if repo.startswith('https://'):
        p = urllib.parse.urlparse(repo)
        scheme = p.scheme or 'https'
        netloc = p.netloc
        return f"{scheme}://{netloc}".rstrip('/')

    if repo.startswith('git@'):
        host = repo.split('@', 1)[1].split(':', 1)[0]
        return f"https://{host}"

    first_part = repo.split('/', 1)[0]
    if '.' in first_part or ':' in first_part:
        return f"https://{first_part}"

    return 'https://gitlab.com'


def _parse_iid(mr_url):
    """Extract the IID (internal ID) from a GitLab Merge Request URL or path.

    Examples it handles:
      - "https://gitlab.com/group/project/-/merge_requests/123" -> "123"
      - "/group/project/-/merge_requests/123" -> "123"
      - "123" -> "123"
      - URLs with query params like "...?iid=123" -> "123"

    Returns the IID as a string if found, otherwise returns None.
    """
    if not mr_url:
        return None
    s = str(mr_url).strip()
    if s.isdigit():
        return s

    p = urllib.parse.urlparse(s)
    path = p.path or s
    query = p.query or ''

    parts = [part for part in path.split('/') if part]
    for part in reversed(parts):
        if part.isdigit():
            return part
    if query:
        qs = urllib.parse.parse_qs(query)
        for key in ('iid', 'id', 'merge_request_iid'):
            vals = qs.get(key)
            if vals:
                v = vals[0]
                if isinstance(v, str) and v.isdigit():
                    return v
    return None

