import logging
from pathlib import Path
from typing import Optional

import jinja2
import questionary
import requests
import yaml

import nf_class
import nf_core.components.create
import nf_core.modules.modules_repo
import nf_core.pipelines.lint_utils
from nf_class.utils import NF_CLASS_MODULES_REMOTE
from nf_core.utils import nfcore_question_style

log = logging.getLogger(__name__)


class ComponentCreateFromClass(nf_core.components.create.ComponentCreate):
    """
    Create a new module or subworkflow from a class.

    Args:
        component_type (str): Type of component to create. [modules|subworkflows]
        directory (str): Directory to create the component in. [default: <current directory>]
        classname (str): Name of the class to create the component from.
        component (str): Name of the component to create.
        author (str): Author of the component.
        force (bool): Overwrite existing files.

    Attributes:
        modules_repo (nf_core.modules.modules_repo.ModulesRepo): Modules repository object.
        classname (str): Name of the class to create the component from.
        inputs_yml (str): Inputs of the class in yaml format.
        outputs_yml (str): Outputs of the class in yaml format.
        inputs (str): Inputs of the class in string format.
        outputs (str): Outputs of the class in string format.

    Raises:
        UserWarning: If trying to create a components for a pipeline instead of a modules repository.
        UserWarning: If the required class name doesn't exist.
    """

    def __init__(
        self,
        component_type: str,
        directory: str = ".",
        classname: str = "",
        component: str = "",
        author: Optional[str] = None,
        force: bool = False,
        modules_repo_url: Optional[str] = NF_CLASS_MODULES_REMOTE,
        modules_repo_branch: Optional[str] = "main",
    ):
        super().__init__(
            component_type=component_type,
            directory=directory,
            component=component,
            author=author,
            process_label=None,
            has_meta=None,
            force=force,
            conda_name=None,
            conda_version=None,
            empty_template=False,
            migrate_pytest=False,
        )
        self.modules_repo = nf_core.modules.modules_repo.ModulesRepo(modules_repo_url, modules_repo_branch)
        self.classname = classname

    def _collect_class_prompt(self) -> None:
        """
        Prompt for the class name.
        """
        available_classes = self._get_available_classes()
        while self.classname is None or self.classname == "":
            self.classname = questionary.autocomplete(
                "Class name:",
                choices=available_classes,
                style=nfcore_question_style,
            ).unsafe_ask()
        if self.classname and self.classname not in available_classes:
            raise UserWarning(f"Class '{self.classname}' not found.")
        # Update subworkflow name based on classname
        if self.component_type == "subworkflows":
            self.component = self.classname

    def _get_available_classes(self, checkout=True, commit=None) -> list:
        """
        Get the available classes from the modules repository.
        """
        if checkout:
            self.modules_repo.checkout_branch()
        if commit is not None:
            self.modules_repo.checkout(commit)

        directory = Path(self.modules_repo.local_repo_dir) / "classes"
        available_classes = [
            fn.split(".yml")[0] for _, _, file_names in directory.walk() for fn in file_names if fn.endswith(".yml")
        ]
        return sorted(available_classes)

    def _get_class_info(self) -> None:
        """
        Get class information from the class yml file.
        """
        # Read class yml
        base_url = f"https://raw.githubusercontent.com/{self.modules_repo.fullname}/{self.modules_repo.branch}/classes/{self.classname}.yml"
        response = requests.get(base_url)
        response.raise_for_status()
        content = yaml.safe_load(response.content)
        # Save attributes
        self.description = content["description"]
        self.keywords = content["keywords"]
        self.inputs_yml = yaml.safe_load(str(content["input"]))
        self.outputs_yml = yaml.safe_load(str(content["output"]))

        if "components" in content and "modules" in content["components"]:
            self.class_modules = content["components"]["modules"]
        else:
            self.class_modules = []
        # Get test data
        self.test_datasets = content["testdata"]

    def _render_template(self) -> None:
        """
        Create new module/subworkflow files with Jinja2.
        """
        # Get all object attributes
        object_attrs = vars(self)

        # Run jinja2 for each file in the template folder
        env = jinja2.Environment(
            loader=jinja2.PackageLoader("nf_class", f"{self.component_type}-template"),
            keep_trailing_newline=True,
        )
        for template_fn, dest_fn in self.file_paths.items():
            log.debug(f"Rendering template file: '{template_fn}'")
            j_template = env.get_template(template_fn)
            try:
                rendered_output = j_template.render(object_attrs)
            except Exception as e:
                log.error(f"Could not render template file '{template_fn}':\n{e}")
                raise e

            # Write output to the target file
            dest_fn.parent.mkdir(exist_ok=True, parents=True)
            with open(dest_fn, "w") as fh:
                log.debug(f"Writing output to: '{dest_fn}'")
                fh.write(rendered_output)
            nf_core.pipelines.lint_utils.run_prettier_on_file(dest_fn)

            # Mirror file permissions
            template_stat = (Path(nf_class.__file__).parent / f"{self.component_type}-template" / template_fn).stat()
            dest_fn.chmod(template_stat.st_mode)
