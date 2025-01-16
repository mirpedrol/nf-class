import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from nf_class.components.create import ComponentCreateFromClass
from nf_class.utils import NF_CLASS_MODULES_REMOTE

log = logging.getLogger(__name__)


class SubworkflowExpandClass(ComponentCreateFromClass):
    """
    Expand a new subworkflow with modules from a class.

    Args:
        classname (str): Name of the class to expand the subworkflow.
        dir (str): Directory to create the subworkflow in. [default: <current directory>]
        author (str): Author of the subworkflow.
        force (bool): Overwrite existing files.
        expand_modules (str): List of modules to expand the subworkflow with.
        modules_repo_url (str): URL of the modules repository.
        modules_repo_branch (str): Branch of the modules repository.
    """

    def __init__(
        self,
        classname: str = "",
        dir: str = ".",
        author: Optional[str] = None,
        force: bool = False,
        expand_modules: str = "",
        modules_repo_url: Optional[str] = NF_CLASS_MODULES_REMOTE,
        modules_repo_branch: Optional[str] = "main",
    ):
        super().__init__(
            "subworkflows",
            dir,
            classname,
            classname,
            author,
            force,
            None,
            None,
            modules_repo_url,
            modules_repo_branch,
        )
        self.classname = classname
        self.expand_modules = expand_modules or ""

    def expand_class(self):
        """Expand the subworkflow with modules from a class."""
        if self.repo_type == "pipelines":
            raise UserWarning("Expanding a subworkflow from a class is not supported for pipelines.")

        if self.directory != ".":
            log.info(f"Base directory: '{self.directory}'")

        # Get the class name
        self._collect_class_prompt()

        self.component_name_underscore = self.component.replace("/", "_")
        self.component_dir = Path(self.component)

        # Check existence of directories early for fast-fail

        self.file_paths = self._get_component_dirs()

        # Prompt for GitHub username
        self._get_username()

        # Add a valid organization name for nf-test tags
        not_alphabet = re.compile(r"[^a-zA-Z]")
        self.org_alphabet = not_alphabet.sub("", self.org)

        # Get the template variables from the class
        self._get_class_info()
        self._get_modules_from_class()
        self._get_info_for_expanding()

        # Create the subworkflow
        self._render_template()
        log.info(f"Created component template: '{self.component}'")

        new_files = [str(path) for path in self.file_paths.values()]
        log.info("Created following files:\n  " + "\n  ".join(new_files))

    def _get_info_for_expanding(self) -> None:
        """Get the information needed to expand the subworkflow with modules from a class."""
        # List of components included in the subworkflow
        self.components: list[str] = [str(component) for component in self.components]
        # List of component tags for nf-tests
        self.components_tags = ""
        for comp in self.components:
            self.components_tags += f"""    tag "{comp}"\n"""

        # Generated code for include statements
        self.include_statements = ""
        for component in self.components:
            self.include_statements += f"""include {{ {component.replace("/", "_").upper()} }} from '../../../modules/{self.org}/{component}/main'\n"""

        # Naming input channels
        input_channels = []
        all_channels_elements = []
        for channel in self.inputs_yml:
            element_keys = []
            for element in channel:
                element_keys.append(list(element.keys())[0])
                all_channels_elements.append(element_keys)
            if element_keys[0] == "meta" or element_keys[0].startswith("meta"):
                input_channels.append(f"ch_{element_keys[1]}")
            else:
                input_channels.append(f"ch_{element_keys[0]}")
        self.input_channels = "\n    ".join(input_channels)

        # Yml input channels
        inputs_yml_swf: dict = {"input": []}
        for i, channel in enumerate(self.inputs_yml):
            inputs_yml_swf["input"].append(
                {
                    input_channels[i]: {
                        "description": f"Channel containing: {", ".join(all_channels_elements[i])}",
                        "structure": channel,
                    }
                }
            )
        self.inputs_yml_swf: str = yaml.dump(inputs_yml_swf)

        # Generate code for output channels
        out_channel_names = []
        for channel in self.outputs_yml:
            out_channel_names.append(list(channel.keys())[0])
        self.output_channels = ""
        for out_channel in out_channel_names:
            self.output_channels += f"    {out_channel} = ch_out_{out_channel}\n"

        # Yml output channels
        outputs_yml_swf: dict = {"output": []}
        for i, channel in enumerate(self.outputs_yml):
            outputs_yml_swf["output"].append(
                {
                    out_channel_names[i]: {
                        "description": f"Output channel {out_channel_names[i]}",
                        "structure": channel[out_channel_names[i]],
                    }
                }
            )
        self.outputs_yml_swf: str = yaml.dump(outputs_yml_swf)

        # Code for running the included module
        self.run_module = ""
        for out_channel in out_channel_names:
            self.run_module += f"    def ch_out_{out_channel} = Channel.empty()\n"
        first = True
        for component in self.components:
            if first:
                start = "if"
                first = False
            else:
                start = "else if"
            module_name = component.replace("/", "_").upper()
            self.run_module += f"""    {start} ( params.{self.classname} == "{component}" ) {{\n        {module_name}( {", ".join(input_channels)} )\n"""
            for out_channel in out_channel_names:
                self.run_module += (
                    f"        ch_out_{out_channel} = ch_out_{out_channel}.mix({module_name}.out.{out_channel})\n"
                )
            self.run_module += "    }\n"

        # nf-tests
        self._generate_nftest_code()

    def _get_modules_from_class(self) -> None:
        """Get the modules belonging to the class."""
        if self.expand_modules != "":
            self.components = self.expand_modules.split(",")
            for module in self.components:
                module_dir = Path(self.directory, "modules", self.org, module)
                if not module_dir.exists():
                    log.info(f"Module '{module}' not found. Skipping.")
                    self.components.remove(module)
        else:
            modules_dir = Path(self.directory, "modules", self.org)
            self.components = []
            for root, dirs, files in modules_dir.walk():
                for module in dirs:
                    if (root / module / "meta.yml").exists():
                        module_name = (root / module).relative_to(modules_dir)
                        with open(root / module / "meta.yml") as fh:
                            meta = yaml.safe_load(fh)
                            if (
                                self._compare_component_class_inputs(meta["input"], self.inputs_yml)
                                and self._compare_component_class_outputs(meta["output"], self.outputs_yml)
                                and set(self.keywords).issubset(meta["keywords"])
                            ):
                                self.components.append(str(module_name))

    def _compare_component_class_inputs(self, component_info: list[list[dict]], class_info: list[list[dict]]) -> bool:
        """Compare the inputs of the class with the component."""
        equal_info = True
        for component_channel, class_channel in zip(component_info, class_info):
            if len(component_channel) == len(class_channel):
                for component_element, class_element in zip(component_channel, class_channel):
                    component_key = list(component_element.keys())[0]
                    class_key = list(class_element.keys())[0]
                    if (
                        component_key != class_key
                        or component_element[component_key]["type"] != class_element[class_key]["type"]
                    ):
                        equal_info = False
                    if "pattern" in component_element[component_key] and "pattern" in class_element[class_key]:
                        if component_element[component_key]["pattern"] != class_element[class_key]["pattern"]:
                            equal_info = False
            else:
                equal_info = False
        return equal_info

    def _compare_component_class_outputs(self, component_info: list[dict], class_info: list[dict]) -> bool:
        """Compare the outputs of the class with the component."""
        equal_info = True
        for component_channel, class_channel in zip(component_info, class_info):
            component_channel_name = list(component_channel.keys())[0]
            class_channel_name = list(class_channel.keys())[0]
            if component_channel_name == class_channel_name:
                for component_element, class_element in zip(
                    component_channel[component_channel_name], class_channel[class_channel_name]
                ):
                    component_key = list(component_element.keys())[0]
                    class_key = list(class_element.keys())[0]
                    if (
                        component_key != class_key
                        or component_element[component_key]["type"] != class_element[class_key]["type"]
                    ):
                        equal_info = False
                    if "pattern" in component_element[component_key] and "pattern" in class_element[class_key]:
                        if component_element[component_key]["pattern"] != class_element[class_key]["pattern"]:
                            equal_info = False
            else:
                equal_info = False
        return equal_info

    def _generate_nftest_code(self) -> None:
        """Generate the code for nf-tests."""
        self.tests = ""
        modules_dir = Path(self.directory, "modules", self.org)
        for component in self.components:
            module_inputs = []
            module_asserts = []
            # Parse module test
            with open(modules_dir / component / "tests" / "main.nf.test") as fh:
                lines = iter(fh.readlines())
                found_input = False
                found_test = False
                setup_code = ""
                for line in lines:
                    if re.sub(r"\s", "", line).startswith("setup") and "{" in line:
                        # This is a composed module
                        while "when {" not in line:
                            if line.strip().startswith("run("):
                                composed_name = line.split('"')[1].lower()
                                composed_name = re.sub(r"_", "/", composed_name)
                                # Add composed module to tags
                                if composed_name not in self.components_tags:
                                    self.components_tags += f"""    tag "{composed_name}"\n"""
                            if line.strip().startswith("script"):
                                # update path for subworkflow
                                line_split = line.split('"')
                                line = (
                                    line_split[0]
                                    + f'"../../../../modules/{self.org}/{composed_name}/main.nf"'
                                    + line_split[2]
                                )
                            setup_code += line
                            line = next(lines)
                    elif re.sub(r"\s", "", line).startswith("process") and "{" in line:
                        # Inputs for the module
                        line = next(lines)
                        while re.sub(r"\s", "", line) != "}":
                            module_inputs.append(line)
                            line = next(lines)
                        found_input = True
                    if "then" in line:
                        while re.sub(r"\s", "", line) != "}":
                            line = re.sub(r"process.", "workflow.", line)
                            if "match(" in line:
                                # give a new name to snapshot to avoid duplications
                                line_split = line.split('"')
                                channel_name = line.split("workflow.out.")[1].split(")")[0]
                                line = line_split[0] + f'"{component.replace("/", "_")}_{channel_name}"' + line_split[2]
                            module_asserts.append(line)
                            line = next(lines)
                        found_test = True
                    if found_input and found_test:
                        break
            # Construct subworkflow tests
            self.tests += f"""    test("run {component}") {{\n\n{setup_code}        when {{\n            params.{self.classname} = "{component}"\n            workflow {{\n{''.join(module_inputs)}            }}\n        }}\n\n{''.join(module_asserts)}        }}\n    }}\n\n"""
