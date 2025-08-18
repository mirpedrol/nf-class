#!/usr/bin/env python
"""nf-class: Wrapper around nf-core/tools to work with class-modules."""

import logging
import os
import sys

import rich
import rich.console
import rich.logging
import rich.traceback
import rich_click as click

from nf_class import __version__
from nf_class.utils import NF_CLASS_MODULES_REMOTE, check_if_outdated, nf_class_logo
from nf_core.utils import rich_force_colors

# Set up logging as the root logger
# Submodules should all traverse back to this
log = logging.getLogger()

# Set up nicer formatting of click cli help messages
click.rich_click.MAX_WIDTH = 100
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.COMMAND_GROUPS = {
    "nf-class": [
        {
            "name": "Commands",
            "commands": [
                "modules",
                "subworkflows",
            ],
        },
    ],
    "nf-class modules": [
        {
            "name": "Developing new modules",
            "commands": ["create-from-class"],
        },
    ],
    "nf-class subworkflows": [
        {
            "name": "Developing new subworkflows",
            "commands": ["expand-class"],
        },
    ],
}

# Set up rich stderr console
stderr = rich.console.Console(stderr=True, force_terminal=rich_force_colors())
stdout = rich.console.Console(force_terminal=rich_force_colors())

# Set up the rich traceback
rich.traceback.install(console=stderr, width=200, word_wrap=True, extra_lines=1)


# Define callback function to normalize the case of click arguments,
# which is used to make the module/subworkflow names, provided by the
# user on the cli, case insensitive.
def normalize_case(ctx, param, component_name):
    if component_name is not None:
        return component_name.casefold()


# Define a custom click group class to sort options and commands in the help message
# TODO: Remove this class and use COMMANDS_BEFORE_OPTIONS when rich-click is updated
# See https://github.com/ewels/rich-click/issues/200 for more information
class CustomRichGroup(click.RichGroup):
    def format_options(self, ctx, formatter) -> None:
        from rich_click.rich_help_rendering import get_rich_options

        self.format_commands(ctx, formatter)
        get_rich_options(self, ctx, formatter)


def run_nf_class():
    # print nf-core header if environment variable is not set
    if os.environ.get("_NF_CORE_COMPLETE") is None:
        # Print nf-core header
        stderr.print("\n")
        for line in nf_class_logo:
            stderr.print(line, highlight=False)
        stderr.print(
            f"\n[grey39]    nf-class version {__version__} - [link=https://github.com/mirpedrol/nf-class]https://github.com/mirpedrol/nf-class[/]",
            highlight=False,
        )
        try:
            is_outdated, _, remote_vers = check_if_outdated()
            if is_outdated:
                stderr.print(
                    f"[bold bright_yellow]    There is a new version of nf-class available! ({remote_vers})",
                    highlight=False,
                )
        except Exception as e:
            log.debug(f"Could not check latest version: {e}")
        stderr.print("\n")
    # Launch the click cli
    nf_class_cli(auto_envvar_prefix="NFCLASS")


@click.group(context_settings=dict(help_option_names=["-h", "--help"]), cls=CustomRichGroup)
@click.version_option(__version__)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Print verbose output to the console.",
)
@click.option("--hide-progress", is_flag=True, default=False, help="Don't show progress bars.")
@click.option("-l", "--log-file", help="Save a verbose log to a file.", metavar="<filename>")
@click.pass_context
def nf_class_cli(ctx, verbose, hide_progress, log_file):
    """
    nf-class is a wrapper to nf.core/tools and provides a set of helper tools for use with class-modules.
    """
    # Set the base logger to output DEBUG
    log.setLevel(logging.DEBUG)

    # Set up logs to the console
    log.addHandler(
        rich.logging.RichHandler(
            level=logging.DEBUG if verbose else logging.INFO,
            console=rich.console.Console(stderr=True, force_terminal=rich_force_colors()),
            show_time=False,
            show_path=verbose,  # True if verbose, false otherwise
            markup=True,
        )
    )

    # don't show rich debug logging in verbose mode
    rich_logger = logging.getLogger("rich")
    rich_logger.setLevel(logging.INFO)

    # Set up logs to a file if we asked for one
    if log_file:
        log_fh = logging.FileHandler(log_file, encoding="utf-8")
        log_fh.setLevel(logging.DEBUG)
        log_fh.setFormatter(logging.Formatter("[%(asctime)s] %(name)-20s [%(levelname)-7s]  %(message)s"))
        log.addHandler(log_fh)

    ctx.obj = {
        "verbose": verbose,
        "hide_progress": hide_progress or verbose,  # Always hide progress bar with verbose logging
    }


# nf-class modules
@nf_class_cli.group()
@click.option(
    "-g",
    "--git-remote",
    type=str,
    default=NF_CLASS_MODULES_REMOTE,
    help="Remote git repo to fetch files from",
)
@click.option(
    "-b",
    "--branch",
    type=str,
    default=None,
    help="Branch of git repository hosting modules.",
)
@click.option(
    "-N",
    "--no-pull",
    is_flag=True,
    default=False,
    help="Do not pull in latest changes to local clone of modules repository.",
)
@click.pass_context
def modules(ctx, git_remote, branch, no_pull):
    """
    Commands to manage Nextflow DSL2 modules (tool wrappers).
    """
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    # Place the arguments in a context object
    ctx.obj["modules_repo_url"] = git_remote
    ctx.obj["modules_repo_branch"] = branch
    ctx.obj["modules_repo_no_pull"] = no_pull


# nf-core modules create-from-class
@modules.command("create-from-class")
@click.pass_context
@click.argument("classname", type=str, callback=normalize_case, required=False, default="", metavar="<class_name>")
@click.option(
    "-t",
    "--toolname",
    type=str,
    callback=normalize_case,
    required=False,
    help="Name of the tool of the module to create.",
    metavar="<tool_name>",
)
@click.option(
    "-d",
    "--dir",
    type=click.Path(exists=True),
    default=".",
    help=r"Modules repository directory. [dim]\[default: current working directory][/]",
    metavar="<directory>",
)
@click.option(
    "-a",
    "--author",
    type=str,
    metavar="<author>",
    help="Module author's GitHub username prefixed with '@'",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite any files if they already exist",
)
@click.option(
    "-c",
    "--conda-name",
    type=str,
    default=None,
    help="Name of the conda package to use",
)
@click.option(
    "-p",
    "--conda-package-version",
    type=str,
    default=None,
    help="Version of conda package to use",
)
def command_modules_create_from_class(
    ctx,
    classname,
    toolname,
    dir,
    author,
    force,
    conda_name,
    conda_package_version,
):
    """
    Create a new DSL2 module from a class-module template.
    """
    from nf_class.modules.create import ModuleCreateFromClass

    try:
        create_obj = ModuleCreateFromClass(
            classname,
            toolname,
            dir,
            author,
            force,
            conda_name,
            conda_package_version,
            ctx.obj["modules_repo_url"],
            ctx.obj["modules_repo_branch"],
        )
        create_obj.create_from_class()
    except UserWarning as e:
        log.error(e)
        sys.exit(1)
    except LookupError as e:
        log.error(e)
        sys.exit(1)


# nf-class subworkflows
@nf_class_cli.group()
@click.option(
    "-g",
    "--git-remote",
    type=str,
    default=NF_CLASS_MODULES_REMOTE,
    help="Remote git repo to fetch files from",
)
@click.option(
    "-b",
    "--branch",
    type=str,
    default=None,
    help="Branch of git repository hosting modules and subworkflows.",
)
@click.option(
    "-N",
    "--no-pull",
    is_flag=True,
    default=False,
    help="Do not pull in latest changes to local clone of modules repository.",
)
@click.pass_context
def subworkflows(ctx, git_remote, branch, no_pull):
    """
    Commands to manage Nextflow DSL2 subworkflows.
    """
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    # Place the arguments in a context object
    ctx.obj["modules_repo_url"] = git_remote
    ctx.obj["modules_repo_branch"] = branch
    ctx.obj["modules_repo_no_pull"] = no_pull


# nf-core subworkflows expand-class
@subworkflows.command("expand-class")
@click.pass_context
@click.argument("classname", type=str, callback=normalize_case, required=False, default="", metavar="<class_name>")
@click.option(
    "-d",
    "--dir",
    type=click.Path(exists=True),
    default=".",
    help=r"Modules repository directory. [dim]\[default: current working directory][/]",
    metavar="<directory>",
)
@click.option(
    "-a",
    "--author",
    type=str,
    metavar="<author>",
    help="Subworkflow author's GitHub username prefixed with '@'",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite any files if they already exist",
)
@click.option(
    "-m",
    "--expand-modules",
    type=str,
    default=None,
    help="Name of the modules the subworkflow should expand, separated by commas. If not provided, all available modules for the class will be expanded.",
)
def command_subworkflows_expand_class(
    ctx,
    classname,
    dir,
    author,
    force,
    expand_modules,
):
    """
    Create a new DSL2 subworkflow from a class.
    """
    from nf_class.subworkflows.create import SubworkflowExpandClass

    try:
        create_obj = SubworkflowExpandClass(
            classname,
            dir,
            author,
            force,
            expand_modules,
            ctx.obj["modules_repo_url"],
            ctx.obj["modules_repo_branch"],
        )
        create_obj.expand_class()
    except UserWarning as e:
        log.error(e)
        sys.exit(1)
    except LookupError as e:
        log.error(e)
        sys.exit(1)


@subworkflows.command("patch")
@click.pass_context
@click.argument("classname", type=str, callback=normalize_case, required=False, metavar="<class_name>")
@click.option(
    "-d",
    "--dir",
    type=click.Path(exists=True),
    default=".",
    help=r"Modules repository directory. [dim]\[default: current working directory][/]",
    metavar="<directory>",
)
def command_subworkflows_patch(
    ctx,
    classname,
    dir,
):
    """
    Patch an existing subworkflow compared with the automatically generated one from expand-class.
    """
    from nf_class.subworkflows.patch import SubworkflowPatch

    try:
        patch_obj = SubworkflowPatch(
            dir,
            ctx.obj["modules_repo_url"],
            ctx.obj["modules_repo_branch"],
            ctx.obj["modules_repo_no_pull"],
        )
        patch_obj.patch(classname)
    except (UserWarning, LookupError) as e:
        log.error(e)
        sys.exit(1)
