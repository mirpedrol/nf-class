"""Tests covering components functions."""

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from git.repo import Repo

import nf_class.classes.expand
import nf_class.classes.patch
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

    def test_expand_class_all(self):
        """Create a subworflows expanding a class. Using all available modules of that class."""

        # Remove existing subworkflow
        shutil.rmtree(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment")

        class_expand = nf_class.classes.expand.ClassExpand(
            classname="msa_alignment",
            dir=self.class_modules,
            author="@me",
        )
        class_expand.expand_class()
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "main.nf").is_file()
        assert (
            self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "tests" / "main.nf.test"
        ).is_file()

        # Check that all modules have been included
        included_modules = []
        should_have_modules = [
            "CLUSTALO_ALIGN",
            "FAMSA_ALIGN",
            "KALIGN_ALIGN",
            "LEARNMSA_ALIGN",
            "MAGUS_ALIGN",
        ]
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "main.nf") as fh:
            for line in fh:
                if line.lstrip().startswith("include"):
                    included_modules.append(line.split()[2])

        for module in should_have_modules:
            assert module in included_modules

    def test_expand_class_specific(self):
        """Create a subworflows expanding a class. Specify which module to add."""

        # Remove existing subworkflow
        shutil.rmtree(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment")

        subworkflow_expand = nf_class.classes.expand.ClassExpand(
            classname="msa_alignment",
            dir=self.class_modules,
            author="@me",
            expand_modules="clustalo/align,famsa/align",
        )
        subworkflow_expand.expand_class()
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "main.nf").is_file()
        assert (
            self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "tests" / "main.nf.test"
        ).is_file()

        # Check that specified modules have been included
        included_modules = []
        should_have_modules = ["CLUSTALO_ALIGN", "FAMSA_ALIGN"]
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "main.nf") as fh:
            for line in fh:
                if line.lstrip().startswith("include"):
                    included_modules.append(line.split()[2])

        assert sorted(included_modules) == sorted(should_have_modules)

    def test_patch_class(self):
        """Patch a subworkflow."""

        # Modify existing subworkflow
        newlines = []
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "main.nf") as fh:
            for line in fh:
                if "CLUSTALO_ALIGN( ch_fasta_branch.clustalo_align, [[], []], [], [], [], [], [] )" in line:
                    new_line = re.sub(
                        r"CLUSTALO_ALIGN\( ch_fasta_branch.clustalo_align, \[\[], \[]], \[], \[], \[], \[], \[] \)",
                        "CLUSTALO_ALIGN( modified )",
                        line,
                    )
                    newlines.append(new_line)
                else:
                    newlines.append(line)
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "main.nf", "w") as fh:
            for line in newlines:
                fh.write(line)

        # Patch subworkflow
        patch_obj = nf_class.classes.patch.ClassPatch(
            self.class_modules,
            NF_CLASS_MODULES_REMOTE,
            no_prompts=True,
        )
        patch_obj.patch("msa_alignment")

        assert (self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "msa_alignment.diff").is_file()
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "msa_alignment.diff") as fh:
            lines = fh.readlines()
            lines = ("").join(lines)
            assert "-    CLUSTALO_ALIGN( ch_fasta_branch.clustalo_align, [[], []], [], [], [], [], [] )" in lines
            assert "+    CLUSTALO_ALIGN( modified )" in lines

    def test_apply_patch(self):
        """Apply a patch to a subworkflow."""

        # Update a subworkflow
        subworkflow_expand = nf_class.classes.expand.ClassExpand(
            classname="msa_alignment",
            dir=self.class_modules,
            author="@me",
            force=True,
        )
        subworkflow_expand.expand_class()

        # Assert patch file is still there and contains some of the expected lines
        assert (self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "msa_alignment.diff").is_file()
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "msa_alignment.diff") as fh:
            lines = fh.readlines()
            lines = ("").join(lines)
            assert '-    test("learnmsa/align") {' in lines
            assert '+    test("learnmsa/align - stub") {' in lines

        # Assert main.nf has the corresponding modifications
        assert (
            self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "tests" / "main.nf.test"
        ).is_file()
        with open(self.class_modules / "subworkflows" / "mirpedrol" / "msa_alignment" / "tests" / "main.nf.test") as fh:
            lines = fh.readlines()
            lines = ("").join(lines)
            print(lines)
            assert 'test("learnmsa/align") {' not in lines
            assert 'test("learnmsa/align - stub") {' in lines
