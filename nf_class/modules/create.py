from typing import Optional

from nf_class.components.create import ComponentCreateFromClass


class ModuleCreateFromClass(ComponentCreateFromClass):
    """
    Create a new module from a class.

    Args:
        classname (str): Name of the class to create the module from.
        component (str): Name of the module to create.
        dir (str): Directory to create the module in. [default: <current directory>]
        author (str): Author of the module.
        force (bool): Overwrite existing files.
        conda_name (str): Name of the conda environment.
        conda_version (str): Version of the conda environment.
        modules_repo_url (str): URL of the modules repository.
        modules_repo_branch (str): Branch of the modules repository.
    """

    def __init__(
        self,
        classname: str = "",
        component: str = "",
        dir: str = ".",
        author: Optional[str] = None,
        force: bool = False,
        conda_name: Optional[str] = None,
        conda_version: Optional[str] = None,
        modules_repo_url: Optional[str] = None,
        modules_repo_branch: Optional[str] = None,
    ):
        super().__init__(
            "modules",
            dir,
            classname,
            component,
            author,
            force,
            conda_name,
            conda_version,
            modules_repo_url,
            modules_repo_branch,
        )
