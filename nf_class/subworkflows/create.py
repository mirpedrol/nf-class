import logging
import re
from pathlib import Path
from typing import Optional

import requests
import yaml

from nf_class.components.create import ComponentCreateFromClass
from nf_class.utils import NF_CLASS_MODULES_REMOTE
from nf_core.pipelines.lint_utils import run_prettier_on_file

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
        self.nfcore_org = "nf-core"

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
        run_prettier_on_file(new_files)
        log.info("Created following files:\n  " + "\n  ".join(new_files))

    def _get_info_for_expanding(self) -> None:
        """Get the information needed to expand the subworkflow with modules from a class."""
        ### List of components included in the subworkflow ###
        self.components: list[str] = [str(component) for component in self.components]
        ### List of component tags for nf-tests ###
        self.components_tags = ""
        for comp in self.components:
            self.components_tags += f"""    tag "{comp}"\n"""

        ### Generated code for include statements ###
        self.include_statements = ""
        for component in self.components:
            self.include_statements += f"""include {{ {component.replace("/", "_").upper()} }} from '../../../modules/{self.nfcore_org}/{component}/main'\n"""

        ### Naming input channels ###
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

        ### Yml input channels ###
        inputs_yml_swf: dict = {"input": []}
        for i, channel in enumerate(self.inputs_yml):
            # Add 'tool' to the channel elements, defines which tool to run
            channel.append(
                {
                    "tool": {
                        "type": "string",
                        "description": "The name of the tool to run",
                    }
                }
            )
            inputs_yml_swf["input"].append(
                {
                    input_channels[i]: {
                        "description": f"Channel containing: {', '.join(all_channels_elements[i])}",
                        "structure": channel,
                    }
                }
            )
        self.inputs_yml_swf: str = yaml.dump(inputs_yml_swf)

        ### Generate code for output channels ###
        out_channel_names = []
        for channel_name in self.outputs_yml:
            out_channel_names.append(channel_name)
        self.output_channels = ""
        for out_channel in out_channel_names:
            self.output_channels += f"    {out_channel} = ch_out_{out_channel}\n"

        ### Yml output channels ###
        outputs_yml_swf: dict = {"output": []}
        for i, channel in enumerate(self.outputs_yml):
            outputs_yml_swf["output"].append(
                {
                    out_channel_names[i]: {
                        "description": f"Output channel {out_channel_names[i]}",
                        "structure": self.outputs_yml[out_channel_names[i]],
                    }
                }
            )
        self.outputs_yml_swf: str = yaml.dump(outputs_yml_swf)

        ### Code for running the included module ###
        self.run_module = ""
        # Declare output channels
        for out_channel in out_channel_names:
            self.run_module += f"    def ch_out_{out_channel} = Channel.empty()\n"
        self.run_module += "\n"
        # Branch input channels
        for i_channel in input_channels:
            channel_elements = i_channel.split("_")[1:]
            self.run_module += f"    {i_channel}\n"
            self.run_module += "        .branch {\n"
            self.run_module += f"            meta, {', '.join(channel_elements)}, tool ->\n"
            for component in self.components:
                module_name = component.replace("/", "_").lower()
                self.run_module += f"""                {module_name}: tool == "{module_name}"\n"""
                self.run_module += f"                    return [ meta, {', '.join(channel_elements)} ]\n"
            self.run_module += "        }\n"
            self.run_module += f"        .set {{ {i_channel + '_branch'} }}\n"
        self.run_module += "\n"
        # Run the included modules
        self.components_args_inputs = {}  # The inputs used for each component
        self.components_names_outputs = {}  # The output channel names of each component matching class output channel names
        for component in self.components:
            # Read component meta.yml file
            base_url = f"https://raw.githubusercontent.com/{self.nfcore_org}/modules/refs/heads/master/modules/{self.nfcore_org}/{component}/meta.yml"
            response = requests.get(base_url)
            response.raise_for_status()
            component_meta = yaml.safe_load(response.content)
            module_name = component.replace("/", "_").upper()
            access_inputs = [f"{i_channel}_branch.{module_name.lower()}" for i_channel in input_channels]
            component_args = self._compare_inputs(component_meta["input"], access_inputs)
            component_outs = self._compare_outputs(component_meta["output"])
            self.components_args_inputs[component] = component_args
            self.components_names_outputs[component] = component_outs
            if component_args:
                self.run_module += f"""    {module_name}( {", ".join(component_args)} )\n"""
            if component_outs:
                for out_channel, comp_out in component_outs.items():
                    self.run_module += (
                        f"    ch_out_{out_channel} = ch_out_{out_channel}.mix({module_name}.out.{comp_out})\n"
                    )
            self.run_module += "\n"

        ### nf-tests ###
        self._generate_nftest_code()

    def _get_modules_from_class(self) -> None:
        """Get the modules belonging to the class."""
        if self.expand_modules != "":
            self.components = self.expand_modules.split(",")
            for module in self.components:
                if module not in self.class_modules:
                    log.info(f"Module '{module}' not found. Skipping.")
                    self.components.remove(module)
        else:
            self.components = self.class_modules[:]

    def _compare_channels(self, component_element, class_element):
        """Compare two channel elements by checking they have teh same type and all the class ontologies are present"""
        if component_element["type"] != class_element["type"]:
            return False
        elif (
            component_element["type"] == "file"
            and "ontologies" in component_element
            and "ontologies" in class_element
            and not all(term in component_element["ontologies"] for term in class_element["ontologies"])
        ):
            return False
        return True

    def _compare_inputs(self, component_info: list[list[dict]], input_channel_names: list[str]) -> Optional[list[str]]:
        """Compare the inputs of the class with the component.
        Returns a list of the different inputs, with empty lists if the input should not be provided."""
        component_run_args = []
        for component_channel in component_info:
            found_channel = False
            for class_channel, ch_name in zip(self.inputs_yml, input_channel_names):
                if type(component_channel) is type(class_channel):
                    if isinstance(component_channel, list):
                        equal_info = True
                        if len(component_channel) == len(class_channel) - 1:  # minus the tool
                            for component_element, class_element in zip(component_channel, class_channel):
                                component_key = list(component_element.keys())[0]
                                class_key = list(class_element.keys())[0]
                                if not self._compare_channels(
                                    component_element[component_key], class_element[class_key]
                                ):
                                    equal_info = False
                                    break
                        else:
                            equal_info = False
                        if equal_info:
                            found_channel = True
                            component_run_args.append(ch_name)
                            break
                    elif isinstance(component_channel, dict):
                        component_key = list(component_channel.keys())[0]
                        class_key = list(class_channel.keys())[0]
                        equal_info = self._compare_channels(component_channel[component_key], class_channel[class_key])
                        if equal_info:
                            found_channel = True
                            component_run_args.append(ch_name)
                            break
            if not found_channel:
                component_run_args.append("[]")

        if all(name in component_run_args for name in input_channel_names):
            return component_run_args
        else:
            return None

    def _compare_outputs(self, component_info: dict) -> Optional[dict]:
        """Compare the outputs of the class with the component.
        Returns a dictionary with the output channel name from the class and the equivalent output channel name from the component."""
        component_out_channels = {}
        for component_ch_name, component_channel in component_info.items():
            for ch_name, class_channel in self.outputs_yml.items():
                if type(component_channel[0]) is type(class_channel[0]):
                    if isinstance(component_channel[0], list):
                        equal_info = True
                        if len(component_channel[0]) == len(class_channel[0]):
                            for component_element, class_element in zip(component_channel[0], class_channel[0]):
                                component_key = list(component_element.keys())[0]
                                class_key = list(class_element.keys())[0]
                                if not self._compare_channels(
                                    component_element[component_key], class_element[class_key]
                                ):
                                    equal_info = False
                                    break
                        else:
                            equal_info = False
                        if equal_info:
                            component_out_channels[ch_name] = component_ch_name
                            break
                    elif isinstance(component_channel[0], dict):
                        component_key = list(component_channel[0].keys())[0]
                        class_key = list(class_channel[0].keys())[0]
                        equal_info = self._compare_channels(
                            component_channel[0][component_key], class_channel[0][class_key]
                        )
                        if equal_info:
                            component_out_channels[ch_name] = component_ch_name
                            break
        if all(name in component_out_channels.keys() for name in self.outputs_yml.keys()):
            return component_out_channels
        else:
            return None

    def _generate_nftest_code(self) -> None:
        """Generate the code for nf-tests."""
        self.tests = ""  # Finall nf-test code

        test_data_per_channel = {}
        for ch_name, test_dataset in zip(self.input_channels.split(), self.test_datasets):
            test_data_per_channel[ch_name] = test_dataset

        for component in self.components:
            test_code = f'\ttest("{component}") {{\n\n'
            test_code += "\t\twhen {\n"
            test_code += "\t\t\tprocess {\n"
            test_code += '\t\t\t\t"""\n'
            if component in self.components_args_inputs:
                component_inputs = self.components_args_inputs[component]
                assert isinstance(component_inputs, list)  # mypy
                for i, input in enumerate(component_inputs):
                    if input != "[]":
                        input_ch_name = input.split(f"_branch.{component.replace('/', '_')}")[0]
                        list_channel = [td.strip('"').strip("'") for td in test_data_per_channel[input_ch_name]]
                        list_channel.append("'" + component.replace("/", "_") + "'")
                        test_code += f"\t\t\t\tinput[{i}] = Channel.of( {', '.join(list_channel)} )\n"
                    else:
                        test_code += f"\t\t\t\tinput[{i}] = Channel.of( {input} )\n"
            test_code += '\t\t\t\t"""\n'
            test_code += "\t\t\t}\n"
            test_code += "\t\t}\n\n"
            test_code += "\t\tthen {\n"
            test_code += "\t\t\tassertAll(\n"
            test_code += "\t\t\t\t{ assert workflow.success },\n"
            test_code += "\t\t\t\t{ assert snapshot(workflow.out).match() },\n"
            test_code += "\t\t\t)\n"
            test_code += "\t\t}\n"
            test_code += "\t}\n\n"
            self.tests += test_code
