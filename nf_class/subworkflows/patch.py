import logging

from nf_class.components.patch import ClassComponentPatch

log = logging.getLogger(__name__)


class SubworkflowPatch(ClassComponentPatch):
    def __init__(self, pipeline_dir, remote_url=None, branch=None, no_pull=False, installed_by=False):
        super().__init__(pipeline_dir, "subworkflows", remote_url, branch, no_pull, installed_by)
