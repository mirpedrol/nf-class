from typing import Optional

from nf_class.components.create import ComponentCreateFromClass


class ModuleCreateFromClass(ComponentCreateFromClass):
    """
    Create a new module from a class.

    Args:
        ctx (dict): Click context object.
        classname (str): Name of the class to create the module from.
        component (str): Name of the module to create.
        dir (str): Directory to create the module in. [default: <current directory>]
        author (str): Author of the module.
        force (bool): Overwrite existing files.
        conda_name (str): Name of the conda environment.
        conda_version (str): Version of the conda environment.
    """

    def __init__(
        self,
        ctx,
        classname: str = "",
        component: str = "",
        dir: str = ".",
        author: Optional[str] = None,
        force: bool = False,
        conda_name: Optional[str] = None,
        conda_version: Optional[str] = None,
    ):
        super().__init__(
            ctx,
            "modules",
            dir,
            classname,
            component,
            author,
            force,
            conda_name,
            conda_version,
        )
