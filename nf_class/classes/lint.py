"""
Code for linting classes and subworkflows expanded from classes
"""

import filecmp
import logging
import operator
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Union

import questionary
import rich.box
import rich.console
import rich.panel
import rich.repr
from rich.markdown import Markdown
from rich.table import Table

import nf_core.modules.modules_repo
from nf_class.classes.expand import ClassExpand
from nf_class.utils import get_available_classes, get_swf_authors
from nf_core.components.components_command import ComponentCommand
from nf_core.components.nfcore_component import NFCoreComponent
from nf_core.pipelines.lint_utils import console
from nf_core.utils import plural_s as _s

log = logging.getLogger(__name__)


class LintExceptionError(Exception):
    """Exception raised when there was an error with module or subworkflow linting"""

    pass


class LintResult:
    """An object to hold the results of a lint test"""

    def __init__(self, component: NFCoreComponent, lint_test: str, message: str, file_path: Path):
        self.component = component
        self.lint_test = lint_test
        self.message = message
        self.file_path = file_path
        self.component_name: str = component.component_name


class ClassLint(ComponentCommand):
    """
    An object for linting classes and subworkflows expanded from a class
    in a 'modules' repository.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        fail_warned: bool = False,
        remote_url: Optional[str] = None,
        branch: Optional[str] = None,
        no_pull: bool = False,
        hide_progress: bool = False,
    ):
        super().__init__(
            "subworkflows",
            directory=directory,
            remote_url=remote_url,
            branch=branch,
            no_pull=no_pull,
            hide_progress=hide_progress,
        )

        self.fail_warned = fail_warned
        self.passed: list[LintResult] = []
        self.warned: list[LintResult] = []
        self.failed: list[LintResult] = []

        if self.repo_type is None:
            raise LookupError(
                "Could not determine repository type. Please check the repository type in the '.nf-core.yml' file"
            )

        if self.repo_type == "pipeline":
            raise LookupError("Ypu can't lint a class in a pipeline repository. Use nf-core linting instead.")

        elif self.repo_type == "modules":
            component_dir = Path(
                self.directory,
                self.default_subworkflows_path,
            )
            self.all_remote_components = [
                NFCoreComponent(m, None, component_dir / m, self.repo_type, self.directory, self.component_type)
                for m in get_available_classes(self.modules_repo)
            ]
            if not self.all_remote_components:
                log.warning(f"No {self.component_type} in '{self.component_type}' directory")

            # This could be better, perhaps glob for all nextflow.config files in?
            self.config = nf_core.utils.fetch_wf_config(self.directory / "tests" / "config", cache_config=True)

    def lint(
        self,
        class_name=None,
        all_classes=False,
        print_results=True,
        show_passed=False,
        sort_by="test",
    ):
        """
        Lint all or one specific class

        First gets a list of all classes. Then lint them.
        The implemented linting tests are:
        - Check that the expanded subworkflow doesn't have untracked changes.

        Args:
            class_name (str):       The name of the class to lint.
            print_results (bool):   Whether to print the linting results
            show_passed (bool):     Whether passed tests should be shown as well
            hide_progress (book):   Don't show progress bars

        Returns:
            ModuleLint object:      Containing information of the passed, warned and failed tests
        """
        if class_name is None and not all_classes and len(self.all_remote_components) > 0:
            questions = [
                {
                    "type": "list",
                    "name": "all_classes",
                    "message": "Lint all classes or a single named class?",
                    "choices": ["All classes", "Named class"],
                },
                {
                    "type": "autocomplete",
                    "name": "class_name",
                    "message": "Class name:",
                    "when": lambda x: x["all_classes"] == "Named class",
                    "choices": [swf.component_name for swf in self.all_remote_components],
                },
            ]
            answers = questionary.unsafe_prompt(questions, style=nf_core.utils.nfcore_question_style)
            all_classes = answers["all_classes"] == "All classes"
            class_name = answers.get("class_name")

        # Only lint the given module
        if class_name:
            if all_classes:
                raise LintExceptionError("You cannot specify a class and request all classes to be linted.")
            to_lint = [swf for swf in self.all_remote_components if swf.component_name == class_name]
            if len(to_lint) == 0:
                raise LintExceptionError(f"Could not find the specified class: '{class_name}'")
        else:
            to_lint = self.all_remote_components

        if self.repo_type == "modules":
            log.info(f"Linting modules repo: [magenta]'{self.directory}'")
        if class_name:
            log.info(f"Linting class: [magenta]'{class_name}'")

        # Lint classes
        if len(to_lint) > 0:
            for swf in to_lint:
                self.class_changes(swf)

        if print_results:
            self._print_results(show_passed=show_passed, sort_by=sort_by)
            self.print_summary()

    def class_changes(self, swf):
        """
        Checks whether the content of a subworkflow has changed compared to the
        subworkflow created when expanding a class.
        """
        # Create a tempdir to expand the class
        tempdir_parent = Path(tempfile.mkdtemp())
        tempdir = tempdir_parent / "tmp_swf_dir"
        author = get_swf_authors(self.directory / swf.component_dir)
        # Copy the current subworkflow to include patch file
        shutil.copytree(self.directory / swf.component_dir, tempdir / swf.component_dir)
        shutil.copy(self.directory / ".nf-core.yml", tempdir)

        expand_obj = ClassExpand(
            classname=swf.component_name,
            dir=tempdir,
            author=author,
            force=True,  # Replace current subworkflow
            modules_repo_url=self.modules_repo.remote_url,
            modules_repo_branch=self.modules_repo.branch,
        )
        expand_obj.expand_class()

        compared_files = self._swf_files_identical(tempdir / swf.component_dir, self.directory / swf.component_dir)

        for f, same in compared_files.items():
            if same:
                self.passed.append(
                    LintResult(
                        component=swf,
                        lint_test="check_files_unchanged",
                        message="Subworkflow files unchanged based on class expanded.",
                        file_path=f"{Path(swf.component_dir, f)}",
                    )
                )
            else:
                self.failed.append(
                    LintResult(
                        component=swf,
                        lint_test="check_files_unchanged",
                        message="Subworkflow files changed based on class expanded.",
                        file_path=f"{Path(swf.component_dir, f)}",
                    )
                )

    def _swf_files_identical(self, swf_path_1, swf_path_2):
        """
        Checks whether two subworkflow files are identical.
        """
        files_to_compare = ["main.nf", "meta.yml", "tests/main.nf.test"]
        files_identical = {file: False for file in files_to_compare}
        for file in files_to_compare:
            try:
                files_identical[file] = filecmp.cmp(Path(swf_path_1, file), Path(swf_path_2, file))
            except FileNotFoundError:
                log.debug(f"Could not open file: {file}")
                continue
        return files_identical

    def _print_results(self, show_passed=False, sort_by="test"):
        """Print linting results to the command line.

        Uses the ``rich`` library to print a set of formatted tables to the command line
        summarising the linting results.
        """

        log.debug("Printing final results")

        sort_order = ["lint_test", "component_name", "message"]
        if sort_by == "module" or sort_by == "subworkflow" or sort_by == "class":
            sort_order = ["component_name", "lint_test", "message"]

        # Sort the results
        self.passed.sort(key=operator.attrgetter(*sort_order))
        self.warned.sort(key=operator.attrgetter(*sort_order))
        self.failed.sort(key=operator.attrgetter(*sort_order))

        # Find maximum module name length
        max_name_len = len(self.component_type[:-1] + " name")
        for tests in [self.passed, self.warned, self.failed]:
            try:
                for lint_result in tests:
                    max_name_len = max(len(lint_result.component_name), max_name_len)
            except Exception:
                pass

        # Helper function to format test links nicely
        def _format_result(test_results, table):
            """
            Given an list of error message IDs and the message texts, return a nicely formatted
            string for the terminal with appropriate ASCII colours.
            """
            last_modname = False
            even_row = False
            for lint_result in test_results:
                if last_modname and lint_result.component_name != last_modname:
                    even_row = not even_row
                last_modname = lint_result.component_name
                module_name = lint_result.component_name

                # Make the filename clickable to open in VSCode
                file_path = os.path.relpath(lint_result.file_path, self.directory)
                file_path_link = f"[link=vscode://file/{os.path.abspath(file_path)}]{file_path}[/link]"

                table.add_row(
                    module_name,
                    file_path_link,
                    Markdown(f"{lint_result.message}"),
                    style="dim" if even_row else None,
                )
            return table

        # Print blank line for spacing
        console.print("")

        # Table of passed tests
        if len(self.passed) > 0 and show_passed:
            table = Table(style="green", box=rich.box.MINIMAL, pad_edge=False, border_style="dim")
            table.add_column(f"{self.component_type[:-1].title()} name", width=max_name_len)
            table.add_column("File path")
            table.add_column("Test message")
            table = _format_result(self.passed, table)
            console.print(
                rich.panel.Panel(
                    table,
                    title=rf"[bold][✔] {len(self.passed)} {self.component_type[:-1].title()} Test{_s(self.passed)} Passed",
                    title_align="left",
                    style="green",
                    padding=0,
                )
            )

        # Table of warning tests
        if len(self.warned) > 0:
            table = Table(style="yellow", box=rich.box.MINIMAL, pad_edge=False, border_style="dim")
            table.add_column(f"{self.component_type[:-1].title()} name", width=max_name_len)
            table.add_column("File path")
            table.add_column("Test message", overflow="fold")
            table = _format_result(self.warned, table)
            console.print(
                rich.panel.Panel(
                    table,
                    title=rf"[bold][!] {len(self.warned)} {self.component_type[:-1].title()} Test Warning{_s(self.warned)}",
                    title_align="left",
                    style="yellow",
                    padding=0,
                )
            )

        # Table of failing tests
        if len(self.failed) > 0:
            table = Table(
                style="red",
                box=rich.box.MINIMAL,
                pad_edge=False,
                border_style="dim",
            )
            table.add_column(f"{self.component_type[:-1].title()} name", width=max_name_len)
            table.add_column("File path")
            table.add_column("Test message", overflow="fold")
            table = _format_result(self.failed, table)
            console.print(
                rich.panel.Panel(
                    table,
                    title=rf"[bold][✗] {len(self.failed)} {self.component_type[:-1].title()} Test{_s(self.failed)} Failed",
                    title_align="left",
                    style="red",
                    padding=0,
                )
            )

    def print_summary(self):
        """Print a summary table to the console."""
        table = Table(box=rich.box.ROUNDED)
        table.add_column("[bold green]LINT RESULTS SUMMARY", no_wrap=True)
        table.add_row(
            rf"[✔] {len(self.passed):>3} Test{_s(self.passed)} Passed",
            style="green",
        )
        table.add_row(rf"[!] {len(self.warned):>3} Test Warning{_s(self.warned)}", style="yellow")
        table.add_row(rf"[✗] {len(self.failed):>3} Test{_s(self.failed)} Failed", style="red")
        console.print(table)
