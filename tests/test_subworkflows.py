"""Tests covering components functions."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from git.repo import Repo

import nf_class.subworkflows.create
from nf_class.utils import NF_CLASS_MODULES_REMOTE


class TestSubworkflows(unittest.TestCase):
    """Class for subworkflows tests."""

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

    def test_create_subworkflow_expand_class_all(self):
        """Create a subworflows expanding a class. Looking for all available modules of that class."""

        subworkflow_expand = nf_class.subworkflows.create.SubworkflowExpandClass(
            classname="alignment",
            dir=self.class_modules,
            author="@me",
        )
        subworkflow_expand.expand_class()
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "alignment" / "main.nf").is_file()
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "alignment" / "tests" / "main.nf.test").is_file()

        # Check that all modules have been included
        included_modules = []
        should_have_modules = [
            "CLUSTALO_ALIGN",
            "FAMSA_ALIGN",
            "KALIGN_ALIGN",
            "LEARNMSA_ALIGN",
            "MAFFT",
            "MAGUS_ALIGN",
            "TCOFFEE_ALIGN",
        ]
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "alignment" / "main.nf") as fh:
            for line in fh:
                if line.lstrip().startswith("include"):
                    included_modules.append(line.split()[2])

        for module in should_have_modules:
            assert module in included_modules

    def test_create_subworkflow_expand_class_specific(self):
        """Create a subworflows expanding a class. Specify which module to add."""

        subworkflow_expand = nf_class.subworkflows.create.SubworkflowExpandClass(
            classname="alignment",
            dir=self.class_modules,
            author="@me",
            expand_modules="clustalo/align,famsa/align",
        )
        subworkflow_expand.expand_class()
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "alignment" / "main.nf").is_file()
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "alignment" / "tests" / "main.nf.test").is_file()

        # Check that specified modules have been included
        included_modules = []
        should_have_modules = ["CLUSTALO_ALIGN", "FAMSA_ALIGN"]
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "alignment" / "main.nf") as fh:
            for line in fh:
                if line.lstrip().startswith("include"):
                    included_modules.append(line.split()[2])

        assert sorted(included_modules) == sorted(should_have_modules)
