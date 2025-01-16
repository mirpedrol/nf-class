# nf-class: Changelog

## v1.0.0dev

- Initial creation of the package
- Add command `nf-class modules create-from-class` [#1](https://github.com/mirpedrol/nf-class/pull/1)
- Add command `nf-class subworkflows expand-class` [#2](https://github.com/mirpedrol/nf-class/pull/2)
- Add pytests [#5](https://github.com/mirpedrol/nf-class/pull/5)
- Handle composed modules when expanding a subworkflow [#6](https://github.com/mirpedrol/nf-class/pull/6)
- Modify `expand-class` command to avoid conditional includes [#8](https://github.com/mirpedrol/nf-class/pull/8)
- Don't allow expanding a subworkflow in a pipelines repo & pin nf-core version [#10](https://github.com/mirpedrol/nf-class/pull/10)
- Remove `prefix` and `suffix` options from `expand-class` command [#11](https://github.com/mirpedrol/nf-class/pull/11)
- Add the class sname to the `meta.yml` of modules [#12](https://github.com/mirpedrol/nf-class/pull/12)
- Fix component name for subworkflows when class name was not provided [#13](https://github.com/mirpedrol/nf-class/pull/13)
