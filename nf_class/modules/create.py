from typing import Optional

from nf_class.components.create import ComponentCreateFromClass


class ModuleCreateFromClass(ComponentCreateFromClass):
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
