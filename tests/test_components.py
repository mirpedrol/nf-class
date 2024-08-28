"""Tests covering components functions."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import requests_cache
import responses
from git.repo import Repo

import nf_class.components.create
from nf_class.utils import NF_CLASS_MODULES_REMOTE

from .utils import mock_anaconda_api_calls


class TestComponents(unittest.TestCase):
    """Class for components tests."""

    def setUp(self):
        """Clone a testing version the mirpedrol/class-modules repo"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.class_modules = Path(self.tmp_dir, "modules-test")

        Repo.clone_from(NF_CLASS_MODULES_REMOTE, self.class_modules, branch="main")

        # Set $PROFILE environment variable to docker - tests will run with Docker
        if os.environ.get("PROFILE") is None:
            os.environ["PROFILE"] = "docker"

    def tearDown(self):
        """Clean up temporary files and folders"""

        # Clean up temporary files
        if self.tmp_dir.is_dir():
            shutil.rmtree(self.tmp_dir)

    def test_create_module_from_class(self):
        """Create a module from a class template."""

        with responses.RequestsMock() as rsps:
            mock_anaconda_api_calls(rsps, "clustalo", "1.2.4")
            rsps.add_passthru("https://raw.githubusercontent.com")
            module_create = nf_class.components.create.ComponentCreateFromClass(
                component_type="modules",
                directory=self.class_modules,
                classname="alignment",
                component="mytestmodule",
                author="@me",
                conda_name="clustalo",
            )
            with requests_cache.disabled():
                module_create.create_from_class()
        assert (self.class_modules / "modules" / "mirpedrol" / "mytestmodule" / "main.nf").is_file()
        assert (self.class_modules / "modules" / "mirpedrol" / "mytestmodule" / "tests" / "main.nf.test").is_file()
