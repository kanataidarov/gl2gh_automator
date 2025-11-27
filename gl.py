import logging as log
import os
import shutil
import subprocess
import sys


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