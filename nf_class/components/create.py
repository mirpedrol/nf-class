import logging
import re
from pathlib import Path
from typing import Optional

import jinja2
import questionary
import requests
import yaml

import nf_class

# import nf_core.components.components_utils
import nf_core.components.create
import nf_core.modules.modules_repo

# TODO: include this once new version of nf-core is released
# import nf_core.pipelines.lint_utils
import nf_core.pipelines.lint_utils
from nf_core.utils import nfcore_question_style

log = logging.getLogger(__name__)


class ComponentCreateFromClass(nf_core.components.create.ComponentCreate):
    """
    Create a new module or subworkflow from a class.

    Args:
        ctx (dict): Click context object.
        component_type (str): Type of component to create. [modules|subworkflows]
        directory (str): Directory to create the component in. [default: <current directory>]
        classname (str): Name of the class to create the component from.
        component (str): Name of the component to create.
        author (str): Author of the component.
        force (bool): Overwrite existing files.
        conda_name (str): Name of the conda environment.
        conda_version (str): Version of the conda environment.

    Attributes:
        modules_repo (nf_core.modules.modules_repo.ModulesRepo): Modules repository object.
        classname (str): Name of the class to create the component from.
        inputs_yml (str): Inputs of the class in yaml format.
        outputs_yml (str): Outputs of the class in yaml format.
        inputs (str): Inputs of the class in string format.
        outputs (str): Outputs of the class in string format.
        input_vars (list): List of input variables.
        output_vars (list): List of output variables.

    Raises:
        UserWarning: If trying to create a components for a pipeline instead of a modules repository.
        UserWarning: If the required class name doesn't exist.
    """

    def __init__(
        self,
        ctx,
        component_type: str,
        directory: str = ".",
        classname: str = "",
        component: str = "",
        author: Optional[str] = None,
        force: bool = False,
        conda_name: Optional[str] = None,
        conda_version: Optional[str] = None,
    ):
        super().__init__(
            component_type=component_type,
            directory=directory,
            component=component,
            author=author,
            process_label=None,
            has_meta=None,
            force=force,
            conda_name=conda_name,
            conda_version=conda_version,
            empty_template=False,
            migrate_pytest=False,
        )
        self.modules_repo = nf_core.modules.modules_repo.ModulesRepo(
            ctx.obj["modules_repo_url"], ctx.obj["modules_repo_branch"]
        )
        self.classname = classname

    def create_from_class(self) -> None:
        """
        Create a new module or subworkflow from a class.
        """
        if self.repo_type == "pipelines":
            raise UserWarning("Creating components from classes is not supported for pipelines.")

        if self.directory != ".":
            log.info(f"Base directory: '{self.directory}'")

        # Get the class name
        self._collect_class_prompt()

        # Get the component name
        self._collect_name_prompt()

        self.component_name = self.component
        self.component_dir = Path(self.component)

        if self.subtool:
            self.component_name = f"{self.component}/{self.subtool}"
            self.component_dir = Path(self.component, self.subtool)

        self.component_name_underscore = self.component_name.replace("/", "_")

        # Check existence of directories early for fast-fail
        self.file_paths = self._get_component_dirs()
        # TODO: remove this lines once the new version of nf-core/tools is released
        self.file_paths.pop("tests/tags.yml")

        if self.component_type == "modules":
            # Try to find a bioconda package for 'component'
            self._get_bioconda_tool()
            # Try to find a biotools entry for 'component'
            # TODO: Add biotools when the nf-core/tools PR is merged to dev
            # self.tool_identifier = nf_core.components.components_utils.get_biotools_id(self.component)

        # Prompt for GitHub username
        self._get_username()

        # Add a valid organization name for nf-test tags
        not_alphabet = re.compile(r"[^a-zA-Z]")
        self.org_alphabet = not_alphabet.sub("", self.org)

        # Get the template variables from the class
        self._get_class_info()

        # Create component template with jinja2
        self._render_template()
        log.info(f"Created component template: '{self.component_name}'")

        new_files = [str(path) for path in self.file_paths.values()]
        log.info("Created following files:\n  " + "\n  ".join(new_files))

    def _get_qualifier(self, type: str) -> str:
        """
        Get the qualifier for the input/output type.
        """
        if type in ["map", "string", "integer", "float", "boolean"]:
            return "val"
        elif type in ["file", "directory"]:
            return "path"
        return ""

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
        self.inputs_yml_str = yaml.dump({"input": self.inputs_yml})
        self.outputs_yml = yaml.safe_load(str(content["output"]))
        self.outputs_yml_str = yaml.dump({"output": self.outputs_yml})
        # Obtain input channels
        self.inputs = ""
        self.input_vars = []
        for channel in content["input"]:
            if len(channel) > 1:
                self.inputs += "tuple "
            first = True
            for element in channel:
                if first:
                    first = False
                else:
                    self.inputs += ", "
                element_name = list(element.keys())[0]
                element_type = element[element_name]["type"]
                qualifier = self._get_qualifier(element_type)
                if any(not c.isalnum() for c in element_name):
                    element_name = f'"{element_name}"'
                self.inputs += f"{qualifier}({element_name})"
                self.input_vars.append(element_name)
            self.inputs += "\n"
        # Obtain input channels
        self.outputs = ""
        self.output_vars = []
        for channel in content["output"]:
            channel_name = list(channel.keys())[0]
            if len(channel[channel_name]) > 1:
                self.outputs += "tuple "
            for element in channel[channel_name]:
                element_name = list(element.keys())[0]
                element_type = element[element_name]["type"]
                qualifier = self._get_qualifier(element_type)
                if any(not c.isalnum() for c in element_name):
                    element_name = f'"{element_name}"'
                self.outputs += f"{qualifier}({element_name}), "
                self.output_vars.append(element_name)
            self.outputs += f"emit: {channel_name}\n\t"

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
            # TODO: change line once new version of nf-core is released
            # nf_core.pipelines.lint_utils.run_prettier_on_file(dest_fn)
            nf_core.pipelines.lint_utils.run_prettier_on_file(dest_fn)

            # Mirror file permissions
            template_stat = (Path(nf_class.__file__).parent / f"{self.component_type}-template" / template_fn).stat()
            dest_fn.chmod(template_stat.st_mode)
