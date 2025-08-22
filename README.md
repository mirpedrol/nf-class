# nf-class

[![code style: prettier](https://img.shields.io/badge/code%20style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v1.json)](https://github.com/charliermarsh/ruff)

Wrapper around nf-core/tools to work with class-modules

## Table of contents

- [Classes of modules](#classes-of-modules)
- [Expanding a class to create a subworkflow](#expanding-a-class-to-create-a-subworkflow)
- [I need to modify the subworkflow](i-need-to-modify-the-subworkflow)

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
components:
  modules:
    - tool/subtool
    - tool2
testdata:
  - - "[ id:'test' ]"
    - "file(params.modules_testdata_base_path + 'path/to/fasta.fasta', checkIfExists: true)"
```

## Expanding a class to create a subworkflow

A `class` definition can be used to generate subworkflow which can run any of the modules belonging to that class.
It is also possible to specify a list of modules form the specified class to avoid adding all possible modules.

This command will create a new subworkflow with the corresponding inputs and outputs and metadata.
A parameter corresponding to the class name is used to slect which module to run.
No parts of the subworkflow should have to be modified manually.

```bash
nf-class classes expand <classname>
```

### Options

- `--dir` `-d`: Modules repository directory. [default: current working directory].
- `--author` `-a`: Subworkflow author's GitHub username prefixed with '@'.
- `--force` `-f`: Overwrite any files if they already exist.
- `--expand-modules` `-m`: Name of the modules the subworkflow should expand, separated by commas. If not provided, all available modules for the class will be expanded.
- `--help` `-h`: Show help message and exit.

### To select which modules to include

In order to select which of the modules of the class to include in the subworkflow,
if you don't want to include all of the available ones,
you can use the `--expand-modules` argument.

```bash
nf-class classes expand <classname> --expand-modules <module_namess>
```

The list of module names should be provided separates by commas and without spaces.
For example:

```bash
nf-class classes expand msa_alignment --expand-modules clustalo/align,famsa/align
```

### To update a subworkflow when a new module has been added

This is done through GitHub actions when the PR to add the new module to the class YAML file is opened.
The command used to update the subwworkflow is the `nf-class classes expand` command with the `--force` argument.
For example:

```bash
nf-class classes expand msa_alignment --force
```

## I need to modify the subworkflow

Sometimes, the generated subworkflow is not quite right.
It can happen that the automatically detected channels are not correct.
Or sometimes the tests don't pass, because they need some extra modification.

If this is your case, you can modify the subworkflow and then _patch_ it.
The patch is required in order to port over the changes once the subworkflow is updated.

Running this command will generate a file `<classname>.diff` in the subworkflow directory.

```bash
nf-class classes expand <classname>
```

### I have added a new module to a class, and I need to modify the subworkflow

If you have an open PR to add a new module to a class, it is possible that you need to modify the newly regenerated subworkflow.
In that case, running the patch command as above will use the class YAML file from the remote repository,
thus ignoring your changes with the new added module.

To patch this subworkflow while you are working on your PR, be sure to provide the proper remote URL and branch.
This is, the remote URL of your fork, and the branch you are working on.
The command will look like this:

```bash
nf-class subworkflows --git-remote <YOUR_REMOTE> --branch <PR_BRANCH> patch <CLASS_NAME>
```
