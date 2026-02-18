#!/usr/bin/env python

from setuptools import find_packages, setup

version = "1.0.0dev"

with open("README.md") as f:
    readme = f.read()

with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name="nf-class",
    version=version,
    description="Wrapper around nf-core/tools to work with class-modules.",
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords=["nf-class", "class-modules", "nf-core", "nextflow", "bioinformatics", "workflow", "pipeline"],
    author="Júlia Mir Pedrol",
    author_email="julia.mir@crg.eu",
    url="https://github.com/mirpedrol/nf-class",
    entry_points={
        "console_scripts": ["nf-class=nf_class.__main__:run_nf_class"],
    },
    python_requires=">=3.9, <4",
    install_requires=required,
    packages=find_packages(exclude=("docs")),
    include_package_data=True,
    zip_safe=False,
)
