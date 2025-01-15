# nf-class

[![code style: prettier](https://img.shields.io/badge/code%20style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v1.json)](https://github.com/charliermarsh/ruff)

Wrapper around nf-core/tools to work with class-modules

## Table of contents

- [Classes of modules](#classes-of-modules)
- [Creating a module form a class](#creating-a-module-from-a-class)
- [Expanding a class subworkflow](#expanding-a-class-subworkflow)

## Classes of modules

A `class` is a way of grouping Nextflow DSL2 modules. All tools which share the same purpose (can be used to perform the same task) and share the same inputs and outputs, belong to the same class.

Essentially, a class is defined through a YAML file specifying the inputs and outputs of that class and some keywords, used to determine the purpose of that class. You can see examples of classes in the [class-modules repository](https://github.com/mirpedrol/class-modules/tree/main/classes).

The basic structure of a class YAML file is the following:

```myclass.yml
# yaml-language-server: $schema=https://raw.githubusercontent.com/mirpedrol/class-modules/main/classes/class-schema.json
name: "myclass"
description: perform the task of this class
keywords:
    - task
    - topic
    - field
input:
    - - meta:
            type: map
            description: Groovy Map containing sample information
      - input1:
            type: file
            description: Input file for this class in FASTA format as an example
            pattern: "*.{fa,fasta}"
            ontologies:
                - edam: http://edamontology.org/format_1929
output:
    - channel1:
        - meta:
            type: map
            description: Groovy Map containing sample information
        - "*.txt"
            type: file
            description: The output file in TXT format of this class
            pattern: "*.txt"
```

## Creating a module form a class

A `class` definition can be used to generate modules which belong to these class.

This command will create a new module with the corresponding inputs and outputs and metadata. Very little parts of the module have to be modified manually:

- The tool command
- The input data for nf-tests
- The assertions and snapshots for nf-tests (if snapshoting the complete output fails)

```bash
nf-class modules create-from-class <classname>
```

### Options

- `--toolname` `-t`: Name of the tool of the module to create.
- `--dir` `-d`: Modules repository directory. [default: current working directory].
- `--author` `-a`: Module author's GitHub username prefixed with '@'.
- `--force` `-f`: Overwrite any files if they already exist.
- `--conda-name` `-c`: Name of the conda package to use.
- `--conda-package-version` `-p`: Version of conda package to use.
- `--help` `-h`: Show help message and exit.

## Expanding a class subworkflow

A `class` definition can be used to generate subworkflow which can run any of the modules belonging to that class.
It is also possible to specify a list of module form the specified class to avoid adding all possible module.

This command will create a new subworkflow with the corresponding inputs and outputs and metadata. A parameter corresponding to the class name is used to slect which module to run.
No parts of the subworkflow should have to be modified manually.

```bash
nf-class subworkflows expand-class <classname>
```

### Options

- `--dir` `-d`: Modules repository directory. [default: current working directory].
- `--author` `-a`: Subworkflow author's GitHub username prefixed with '@'.
- `--force` `-f`: Overwrite any files if they already exist.
- `--expand-modules` `-m`: Name of the modules the subworkflow should expand, separated by commas. If not provided, all available modules for the class will be expanded.
- `--help` `-h`: Show help message and exit.
