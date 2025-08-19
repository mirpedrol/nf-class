import logging
import os
import shutil
import tempfile
from pathlib import Path

import questionary
import ruamel.yaml

from nf_class.subworkflows.create import SubworkflowExpandClass
from nf_core.components.components_command import ComponentCommand
from nf_core.components.components_differ import ComponentsDiffer
from nf_core.utils import nfcore_question_style

log = logging.getLogger(__name__)


class ClassComponentPatch(ComponentCommand):
    def __init__(self, pipeline_dir, component_type, remote_url=None, branch=None, no_pull=False, installed_by=None):
        super().__init__(component_type, pipeline_dir, remote_url, branch, no_pull)

    def _parameter_checks(self, component, components):
        """Checks the compatibility of the supplied parameters.

        Raises:
            UserWarning: if any checks fail.
        """
        if not self.repo_type == "modules":
            raise UserWarning(
                f"The 'nf-class {self.component_type} patch' command can only be run in a modules repository."
            )
        if self.org == "nf-core":
            raise UserWarning(
                f"The 'nf-class {self.component_type} patch' command can only be run in custome modules repositories, not in the nf-core organisation."
            )
        if not self.has_valid_directory():
            raise UserWarning("The command was not run in a valid modules repository.")

        if component is not None and component not in components:
            raise UserWarning(
                f"{self.component_type[:-1].title()} '{Path(self.component_type, self.modules_repo.repo_path, component)}' not found in the modules repo: {self.modules_repo.remote_url}."
            )

    def patch(self, component=None):
        components = self.modules_repo.get_avail_components(self.component_type)
        self._parameter_checks(component, components)

        if component is None:
            component = questionary.autocomplete(
                f"{self.component_type[:-1].title()} name:",
                choices=sorted(components),
                style=nfcore_question_style,
            ).unsafe_ask()
        component_dir = self.modules_repo.repo_path
        component_fullname = str(Path(self.component_type, component_dir, component))
        component_relpath = Path(self.component_type, component_dir, component)

        # Set the diff filename based on the component name
        patch_filename = f"{component.replace('/', '-')}.diff"
        patch_relpath = Path(component_relpath, patch_filename)
        component_current_dir = Path(self.directory, component_relpath)
        patch_path = Path(self.directory, patch_relpath)

        if patch_path.exists():
            remove = questionary.confirm(
                f"Patch exists for {self.component_type[:-1]} '{component_fullname}'. Do you want to regenerate it?",
                style=nfcore_question_style,
            ).unsafe_ask()
            if remove:
                os.remove(patch_path)
            else:
                return

        # Get info from current subworkflow
        yaml = ruamel.yaml.YAML()
        with open(component_relpath / "meta.yml") as fh:
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

        # Create a class
        try:
            expand_class_obj = SubworkflowExpandClass(
                classname=component,
                dir=install_dir,
                author=author,
            )
            component_install_dir = Path(install_dir, self.component_type, self.org, component)
            expand_class_obj.expand_class()
        except UserWarning as e:
            raise UserWarning(f"Failed to expand class '{component}' from remote ({self.modules_repo.remote_url}): {e}")

        # Write the patch to a temporary location (otherwise it is printed to the screen later)
        patch_temp_path = tempfile.mktemp()
        try:
            ComponentsDiffer.write_diff_file(
                patch_temp_path,
                component,
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
            component,
            self.modules_repo.repo_path,
            component_install_dir,
            component_current_dir,
            dsp_from_dir=component_current_dir,
            dsp_to_dir=component_current_dir,
        )

        # Finally move the created patch file to its final location
        shutil.move(patch_temp_path, patch_path)
        log.info(f"Patch file of '{component_fullname}' written to '{patch_path}'")
