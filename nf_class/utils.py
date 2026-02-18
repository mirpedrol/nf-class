import concurrent.futures
import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests
import ruamel
from packaging.version import Version

import nf_class

log = logging.getLogger(__name__)

NF_CLASS_MODULES_REMOTE = "https://github.com/mirpedrol/class-modules.git"
nf_class_logo = [
    r"[green]                                        ",
    r"[blue]          ___     __       __   __  __   ",
    r"[blue]    |\ | |__  __ /  ` |   |__| /__ /__   ",
    r"[blue]    | \| |       \__, |__ |  | __/ __/   ",
    r"[green]                                        ",
]


def fetch_remote_version(source_url):
    response = requests.get(source_url, timeout=3)
    remote_version = re.sub(r"[^0-9\.]", "", response.data.tag_name)
    return remote_version


def check_if_outdated(
    current_version=None, remote_version=None, source_url="https://github.com/mirpedrol/nf-class/releases/latest"
):
    """
    Check if the current version of nf-class is outdated
    """
    # Exit immediately if disabled via ENV var
    if os.environ.get("NFCLASS_NO_VERSION_CHECK", False):
        return (True, "", "")
    # Set and clean up the current version string
    if current_version is None:
        current_version = nf_class.__version__
    current_version = re.sub(r"[^0-9\.]", "", current_version)
    # Build the URL to check against
    source_url = os.environ.get("NFCLASS_VERSION_URL", source_url)
    source_url = f"{source_url}?v={current_version}"
    # check if we have a newer version without blocking the rest of the script
    is_outdated = False
    if remote_version is None:  # we set it manually for tests
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_remote_version, source_url)
                remote_version = future.result()
        except Exception as e:
            log.debug(f"Could not check for nf-class updates: {e}")
    if remote_version is not None:
        if Version(remote_version) > Version(current_version):
            is_outdated = True
    return (is_outdated, current_version, remote_version)


def get_swf_authors(swf_dir: Path) -> Optional[str]:
    """Get the author of a subworkflow"""
    yaml = ruamel.yaml.YAML()
    with open(swf_dir / "meta.yml") as fh:
        meta_yaml = yaml.load(fh)
    author = None
    authors = meta_yaml.get("authors", None)
    if authors is not None:
        author = authors[0]
    return author


def get_available_classes(modules_repo, checkout=True, commit=None) -> list:
    """
    Get the available classes from the modules repository.
    """
    if checkout:
        modules_repo.checkout_branch()
    if commit is not None:
        modules_repo.checkout(commit)

    directory = Path(modules_repo.local_repo_dir) / "classes"
    available_classes = [
        fn.split(".yml")[0] for _, _, file_names in os.walk(directory) for fn in file_names if fn.endswith(".yml")
    ]
    return sorted(available_classes)
