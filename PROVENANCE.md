# Provenance

Author: Palakurthi Gowri Shankar.

Dates and identifiers for this repository and the specification it
implements. Commit and tag dates are the ones git records, from the
author's clock; the GitHub and Software Heritage records are kept by
those services.

## sabline-lang

| What | Identifier | Date |
|---|---|---|
| Repository | <https://github.com/gowrishankar-infra/sabline-lang> | created on GitHub 2026-08-16T18:43:04Z |
| First commit of the effect system: `uses` clauses and the transitive effect checker, `check_effects`. It is also the repository's first commit. | `dcb44e2310291fa546405434f4698148413f3cdd`, "Sabline v0.9: effects + types + contracts + Z3 proofs + LLVM native" | 2026-08-17T00:21:33+05:30 |
| First commit enforcing an effect budget while a program runs (`--allow`, `--deny`) | `dc4e3a1ecea285dae6c088507bd6d1651fec6093`, v2.40 | 2026-08-18T21:55:51+05:30 |
| Budgets scoped to paths, hosts and counts; `env` its own effect | `a76c217d0cf5dd1539e5c895576ad507740ab2a3`, v3.0.0 | 2026-09-10T23:00:21+05:30 |
| The capability ratchet (`sabline.capabilities/1`) | `ae7a04102cc9d0704be659036bcd2c535983f036`, v4.0.0; GitHub release published 2026-09-11T08:11:46Z | 2026-09-11T13:41:12+05:30 |
| The conformance corpus, citation files, the predicate type | `3c81ed1353d3dc1aeec2779329ce59e324f39114`, v4.1.0; GitHub release published 2026-09-11T10:40:34Z | 2026-09-11T16:09:50+05:30 |
| `sabline attest`, a producer of the predicate type | `53fa3cb5c008d202dec6abf56e76d496d4221da3`, v4.2.0; GitHub release published 2026-09-11T14:52:36Z | 2026-09-11T19:50:49+05:30 |
| The author's name with a capital S | 4.2.1, tag `v4.2.1` | 2026-09-11 |
| `Money of CUR`, an exact amount whose split is proven to add up | 4.3.0, tag `v4.3.0` | 2026-09-12 |
| A proof that runs out of time says so, and a discount rule that cannot go negative | 4.3.1, tag `v4.3.1` | 2026-09-12 |
| The language card's size stated correctly, and the MCP registry manifest on the registry's current schema | 4.3.2, tag `v4.3.2` | 2026-09-12 |
| `sabline mcp`, so the npm package can start the MCP server too | 4.3.3, tag `v4.3.3` | 2026-09-12 |
| The npm wrapper picks the right Python, and says when it cannot | 4.3.4, tag `v4.3.4` | 2026-09-12 |
| This version: a reference service showing how a platform lets its customers write Sabline | 4.4.0, tag `v4.4.0` | 2026-09-12 |

## sabline-spec

| What | Identifier | Date |
|---|---|---|
| Repository | <https://github.com/gowrishankar-infra/sabline-spec> | created on GitHub 2026-09-11T03:29:01Z |
| v0.1, the capability format as first written down, extracted from sabline-lang 3.1.1 (`25d2c051bb5f6925006fed2d44ba8fe809b8cf36`) | annotated tag `v0.1` on commit `f4e7babe7e961d35f6b31450c6d42f3860123acf` | tagged 2026-09-11T08:58:50+05:30 |
| v0.4, with the conformance corpus | tag `v0.4` on commit `2bf8bbe189a81582772b5c6549cef6fda18524e2` | tagged 2026-09-11T16:09:41+05:30 |
| v0.5, recording the producer `sabline attest` | tag `v0.5` on commit `f6ac9896b9204ea3b658b3d685c5b21ee257069f` | tagged 2026-09-11T19:51:32+05:30 |
| v0.5.1, the author's name with a capital S | tag `v0.5.1` | 2026-09-11 |

sabline-lang is the reference implementation of sabline-spec.

## Software Heritage

Both repositories were submitted to the Software Heritage archive
through its save-code-now API
(`POST https://archive.softwareheritage.org/api/1/origin/save/git/url/<origin>/`),
twice. The request ids, request dates, visit dates and snapshot
identifiers are the ones the API returned.

The first pair was requested just before sabline-lang 4.1.0 and
sabline-spec 0.4 were pushed, and the archive visited before the push,
so these snapshots hold the history up to sabline-lang 4.0.1 and
sabline-spec 0.3:

| Origin | Save request | Requested (UTC) | Visited (UTC) | Snapshot | `main` in the snapshot |
|---|---|---|---|---|---|
| https://github.com/gowrishankar-infra/sabline-lang | 2471043 | 2026-09-11T10:39:14.948887Z | 2026-09-11T10:39:19.973Z | `swh:1:snp:e4b061fba4098c65f910059d6e3a7c36c7b06e82` | `c080c9f140d06f56a067ff373a09ab89ca76d4c7` (4.0.1) |
| https://github.com/gowrishankar-infra/sabline-spec | 2471044 | 2026-09-11T10:39:16.118803Z | 2026-09-11T10:39:20.075Z | `swh:1:snp:cd54a6a90ef956dcc767b5e3340ff6ad8e18a2a6` | `e2622eb3ba87edd233cdc6fdbfe9113d16bd70d8` (0.3) |

The second pair was requested after the 4.1.0 and 0.4 push; these are
the snapshots taken after it, holding tags `v4.1.0` and `v0.4`:

| Origin | Save request | Requested (UTC) | Visited (UTC) | Snapshot | `main` in the snapshot |
|---|---|---|---|---|---|
| https://github.com/gowrishankar-infra/sabline-lang | 2471049 | 2026-09-11T10:41:21.003154Z | 2026-09-11T10:41:22.251Z | `swh:1:snp:9d8d969d83aac1f1970d5d08ba3755085f28f82c` | `3c81ed1353d3dc1aeec2779329ce59e324f39114` (4.1.0) |
| https://github.com/gowrishankar-infra/sabline-spec | 2471050 | 2026-09-11T10:41:22.084845Z | 2026-09-11T10:41:32.013Z | `swh:1:snp:578ec668186a85ea1eeb8c0a14d77736d3e40186` | `2bf8bbe189a81582772b5c6549cef6fda18524e2` (0.4) |

A save request's record is at
`https://archive.softwareheritage.org/api/1/origin/save/<id>/`, and the
archive's list of each origin's visits at
<https://archive.softwareheritage.org/browse/origin/visits/?origin_url=https://github.com/gowrishankar-infra/sabline-lang>
and
<https://archive.softwareheritage.org/browse/origin/visits/?origin_url=https://github.com/gowrishankar-infra/sabline-spec>.
