# Vendored test data

`sarif-schema-2.1.0.json` is the SARIF 2.1.0 JSON Schema (Errata 01,
OASIS Standard), fetched once from

    https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json

on 2026-09-11, byte for byte. Its sha256 is

    c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e

and the copy in the OASIS repository
(`oasis-tcs/sarif-spec`, `sarif-2.1/schema/sarif-schema-2.1.0.json`)
has the same bytes. `check_library.py` checks that digest before it
validates `sabline check --sarif`, `sabline proofs --sarif` and
`sabline audit --sarif` against the schema, so the schema cannot be
edited to make the output pass. `.gitattributes` keeps git from changing
its line endings.
