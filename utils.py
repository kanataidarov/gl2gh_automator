import os
import json
import logging as log
import urllib.request
import urllib.error

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
GITLAB_HOST = os.getenv('GITLAB_HOST', 'https://gitlab.com')


def parse_github_owner_repo(url):
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


def github_api_request(path, method='GET', data=None, headers=None):
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


def get_authenticated_user():
    code, body = github_api_request('/user')
    if code == 200 and body and 'login' in body:
        return body['login']
    log.warning(f"Couldn't determine authenticated GitHub user (status {code}). Proceeding without user-check.")
    return None


# --- GitLab helpers ---

def gitlab_api_request(path, method='GET', data=None, headers=None, gitlab_host=None):
    """Make a request to the GitLab REST API and return (status_code, json_body-or-None).
    path should start with '/'. Example: '/projects/:id/merge_requests'.
    """
    host = gitlab_host or GITLAB_HOST
    url = f"{host}/api/v4{path}"
    req_headers = {
        'User-Agent': 'gl2gh-automator',
        'Accept': 'application/json'
    }
    # Prefer Authorization header but support PRIVATE-TOKEN header
    if GITLAB_TOKEN:
        req_headers['Authorization'] = f'Bearer {GITLAB_TOKEN}'
    else:
        # no token provided -> will likely fail; keep going
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


def gitlab_parse_project_id(gitlab_repo):
    """Accepts either a URL (https://gitlab.com/group/project(.git)) or a path like group/project
    Returns URL-encoded project path suitable for /projects/:id endpoints (e.g. 'group%2Fproject')
    If gitlab_repo looks numeric, returns it unchanged.
    """
    repo = gitlab_repo
    if repo.startswith('https://'):
        # strip scheme and possible host prefix
        if 'gitlab.com/' in repo:
            repo = repo.split('gitlab.com/')[-1]
        else:
            # strip scheme and hostname
            repo = repo.split('://', 1)[-1].split('/', 1)[-1]
    repo = repo.rstrip('/')
    if repo.endswith('.git'):
        repo = repo[:-4]
    # if looks like numeric id
    if repo.isdigit():
        return repo
    # URL-encode slashes to %2F
    return repo.replace('/', '%2F')
