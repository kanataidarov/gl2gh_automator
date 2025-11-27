import os
import json
import logging as log
import urllib.request
import urllib.error

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')


def parse_github_owner_repo(url):
    if url.startswith("https://"):
        path = url.split('https://github.com/')[1]
    elif url.startswith("http://"):
        path = url.split('http://github.com/')[1]
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
        try:
            err_body = e.read().decode('utf-8')
            return e.code, json.loads(err_body) if err_body else None
        except Exception:
            return e.code, None
    except Exception as e:
        log.error(f"GitHub API request failed: {e}")
        return None, None


def get_authenticated_user():
    code, body = github_api_request('/user')
    if code == 200 and body and 'login' in body:
        return body['login']
    log.warning(f"Couldn't determine authenticated GitHub user (status {code}). Proceeding without user-check.")
    return None

