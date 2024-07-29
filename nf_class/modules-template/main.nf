process {{ component_name_underscore|upper }} {
    tag "$meta.id"
    label '{{ process_label }}'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        '{{ singularity_container if singularity_container else 'https://depot.galaxyproject.org/singularity/YOUR-TOOL-HERE' }}':
        '{{ docker_container if docker_container else 'biocontainers/YOUR-TOOL-HERE' }}' }"

    input:
    {{ inputs }}

    output:
    {{ outputs }}

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    // TODO nf-class: Update the command to run the tool
    """
    {{ component }} \
        -t ${task.cpus} \
        $args \
        {{ input_vars | join('\\ \n\t\t') }} \
        {{ output_vars | join('\\ \n\t\t') }}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        {{ component }}: \$( {{ component }} --version )
    END_VERSIONS
    """

    stub:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    // TODO nf-class: Update the output files to generate
    """
    touch {{ output_vars | join('\\ \n\t\t') }}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        {{ component }}: \$( {{ component }} --version )
    END_VERSIONS
    """
}
