import logging
import os
import shutil
import tempfile
from pathlib import Path

import questionary
import ruamel.yaml

from nf_class.classes.expand import ClassExpand
from nf_core.components.components_command import ComponentCommand
from nf_core.components.components_differ import ComponentsDiffer
from nf_core.utils import nfcore_question_style

log = logging.getLogger(__name__)


class ClassPatch(ComponentCommand):
    """
    Create a patch for the class subworkflow comparing it with the subworkflow generated form the class YAML file.

    Args:
        local_repo_path (str | Path): Path to the local directory of the modules repo.
        remote_url (str | None): Remote URL to the modules repo.
        branch (str | None): The branch from the remote modules repo to use.
        no_pull (bool): Do not pull in latest changes to local clone of modules repository.
        no_prompts (book): If skip all interactive prompts.

    Raises:
        UserWarning: If trying to patch in a pipeline repo or nf-core/modules repo.
        UserWarning: If the provided path is not a valid modules repo
        UserWarning: If the class doesn't exist.
        UserWarning: Any other error while creating the patch.
    """

    def __init__(
        self, local_repo_path: str | Path = ".", remote_url=None, branch=None, no_pull=False, no_prompts=False
    ):
        super().__init__("subworkflows", local_repo_path, remote_url, branch, no_pull, no_prompts=no_prompts)
        self.remote_url: str | None = remote_url
        self.branch: str | None = branch

    def _parameter_checks(self, classname, components):
        """Checks the compatibility of the supplied parameters.

        Raises:
            UserWarning: if any checks fail.
        """
        if not self.repo_type == "modules":
            raise UserWarning("The 'nf-class class patch' command can only be run in a modules repository.")
        if self.org == "nf-core":
            raise UserWarning(
                "The 'nf-class class patch' command can only be run in custome modules repositories, not in the nf-core organisation."
            )
        if not self.has_valid_directory():
            raise UserWarning("The command was not run in a valid modules repository.")

        if classname is not None and classname not in components:
            raise UserWarning(
                f"Subworkflow '{Path(self.component_type, self.modules_repo.repo_path, classname)}' not found in the modules repo: {self.modules_repo.remote_url} branch {self.modules_repo.branch}."
            )

    def patch(self, classname=None):
        components = self.modules_repo.get_avail_components(self.component_type)
        self._parameter_checks(classname, components)

        if classname is None:
            classname = questionary.autocomplete(
                "Class name:",
                choices=sorted(components),
                style=nfcore_question_style,
            ).unsafe_ask()
        component_dir = self.modules_repo.repo_path
        component_fullname = str(Path(self.component_type, component_dir, classname))
        component_relpath = Path(self.component_type, component_dir, classname)

        # Set the diff filename based on the component name
        patch_filename = f"{classname}.diff"
        patch_relpath = Path(component_relpath, patch_filename)
        component_current_dir = Path(self.directory, component_relpath)
        patch_path = Path(self.directory, patch_relpath)

        if patch_path.exists() and not self.no_prompts:
            remove = questionary.confirm(
                f"Patch exists for subworkflow '{component_fullname}'. Do you want to regenerate it?",
                style=nfcore_question_style,
            ).unsafe_ask()
            if remove:
                os.remove(patch_path)
            else:
                return
        elif patch_path.exists() and self.no_prompts:
            os.remove(patch_path)

        # Get info from current subworkflow
        yaml = ruamel.yaml.YAML()
        with open(component_current_dir / "meta.yml") as fh:
            meta_yaml = yaml.load(fh)
        author = None
        authors = meta_yaml.get("authors", None)
        if authors is not None:
            author = authors[0]

        # Create a temporary directory for storing the bare generated subworkflow
        install_dir = tempfile.mkdtemp()
        # Copy .nf-core.yml from current modules repo in self.directory to install_dir
        src_nfcore_yml = Path(self.directory) / ".nf-core.yml"
        dst_nfcore_yml = Path(install_dir) / ".nf-core.yml"
        if src_nfcore_yml.exists():
            shutil.copy(src_nfcore_yml, dst_nfcore_yml)

        # Create a class subworkflow
        try:
            expand_class_obj = ClassExpand(
                classname=classname,
                dir=install_dir,
                author=author,
                modules_repo_url=self.remote_url,
                modules_repo_branch=self.branch,
            )
            component_install_dir = Path(install_dir, self.component_type, self.org, classname)
            expand_class_obj.expand_class()
        except UserWarning as e:
            raise UserWarning(
                f"Failed to expand class '{classname}' from remote ({self.modules_repo.remote_url}) and branch ({self.modules_repo.branch}): {e}"
            )

        # Write the patch to a temporary location (otherwise it is printed to the screen later)
        patch_temp_path = tempfile.mktemp()
        try:
            ComponentsDiffer.write_diff_file(
                patch_temp_path,
                classname,
                self.modules_repo.repo_path,
                component_install_dir,
                component_current_dir,
                for_git=False,
                dsp_from_dir=component_relpath,
                dsp_to_dir=component_relpath,
            )
            log.debug(f"Patch file wrote to a temporary directory {patch_temp_path}")
        except UserWarning:
            raise UserWarning(f"Class '{component_fullname}' is unchanged. No patch to compute")

        # Show the changes made to the module
        ComponentsDiffer.print_diff(
            classname,
            self.modules_repo.repo_path,
            component_install_dir,
            component_current_dir,
            dsp_from_dir=component_current_dir,
            dsp_to_dir=component_current_dir,
        )

        # Finally move the created patch file to its final location
        shutil.move(patch_temp_path, patch_path)
        log.info(f"Patch file of '{component_fullname}' written to '{patch_path}'")
