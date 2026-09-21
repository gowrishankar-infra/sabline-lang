# Maintainers

## Today

- **Palakurthi Gowri Shankar** ([@gowrishankar-infra](https://github.com/gowrishankar-infra))
  — author, and currently the only maintainer.

That is a real risk for anyone depending on this project, stated
plainly in [SUPPORT.md](SUPPORT.md). The rest of this file exists to
make it easy to change.

## How someone becomes a maintainer

No interview, no quota. The path is:

1. Land a few changes — a fix, a test, a documentation correction, an
   example. Size does not matter; care does.
2. Show judgement in review: catching what a change breaks, or saying
   "this is not worth the complexity", is worth more than volume.
3. Ask, or be asked. Commit access follows from having behaved like a
   maintainer for a while.

A maintainer can merge, release, and speak for the project's
direction. The one thing a maintainer may not do is weaken a
guarantee quietly — if a change makes "proven" mean less than it does
today, it needs to be said out loud, in the changelog, in those words.

## Good places to start

These are real, small and self-contained:

- **`sabline.toml` for projects** — a place to record which files are
  a project, so `sabline check` needs no arguments.
- **Dates arithmetic** in `stdlib/dates.vel`: adding days across month
  and year boundaries, with proven promises.
- **`json_set(doc, path, value)`** to go with the readers.
- **A `Duration` type** in the standard library.
- **Better `explain` output for large projects** — grouping, filtering.
- **Proof reasons**: when a promise is not proven, say which part the
  solver could not settle.

Each of these fits in one file, has an obvious test, and does not
require understanding the whole compiler. [ARCHITECTURE.md](ARCHITECTURE.md)
says where things live.

## What review looks like

Changes are read for three things, in order: does it keep the
guarantees ([ARCHITECTURE.md](ARCHITECTURE.md) "The rules this project
holds"), does it have a test that would fail without it, and is it
written so the next person can follow it. Formatting and style are the
formatter's job, not a reviewer's.
