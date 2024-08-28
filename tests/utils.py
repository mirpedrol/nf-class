"""Helper functions for tests"""

import responses


def mock_anaconda_api_calls(rsps: responses.RequestsMock, module: str, version: str) -> None:
    """Mock anaconda api calls for module"""
    anaconda_api_url = f"https://api.anaconda.org/package/bioconda/{module}"
    anaconda_mock = {
        "latest_version": version.split("--")[0],
        "summary": "",
        "doc_url": "http://test",
        "dev_url": "http://test",
        "files": [{"version": version.split("--")[0]}],
        "license": "MIT",
    }
    rsps.get(anaconda_api_url, json=anaconda_mock, status=200)
