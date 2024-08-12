{{ include_statements }}

workflow {{ component_name_underscore|upper }} {

    take:
    {{ input_channels }}

    main:

    ch_versions = Channel.empty()

    {{ run_module }}
    ch_versions = ch_versions.mix({{ classname|upper }}.out.versions)

    emit:
{{ output_channels }}
}

