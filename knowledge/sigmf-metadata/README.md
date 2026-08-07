# sigmf-metadata — the community metadata format

A `.sigmf-meta` JSON sidecar + a `.sigmf-data` payload file. The sidecar
carries `core:sample_rate`, `core:datatype`, `core:frequency`,
`core:datetime`, plus optional per-segment annotations. Prefer SigMF for
archival captures — the sidecar retains everything a bare `.cs8` file
loses.
