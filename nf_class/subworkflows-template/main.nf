{{ include_statements }}

workflow {{ component_name_underscore|upper }} {

    take:
    {{ input_channels }}

    main:
{{ run_module }}

    emit:
{{ output_channels }}
}

