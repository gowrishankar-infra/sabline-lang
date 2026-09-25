# Access to everything, or nothing? Giving an agent's code only what the task needs

<!-- description: A budget between everything and nothing: one folder to read, one to write, one host, a number of operations - and a refusal the moment a program reaches past it. -->

> "I shouldn't have to decide between giving a model access to *everything*
> I can access, or *nothing*." - a commenter on the
> [GitHub MCP exploit thread](https://news.ycombinator.com/item?id=44103863)
> on Hacker News, 27 May 2025.

The complaint recurs because the choice is often really that coarse. Claude
Desktop's installer for MCP extensions warns "Installing will grant access
to everything on your computer" (as quoted in
[modelcontextprotocol/mcpb#177](https://github.com/modelcontextprotocol/mcpb/issues/177),
filed 2026-01-07), and an agent's shell is usually either unrestricted or
asks about every command. This guide shows the ground in between, for code
written in Sabline: a budget that names one folder, one host, or a number of
operations, and refuses the rest when it is tried.

> [!NOTE]
> **What this does not do.** A budget bounds a program written in Sabline;
> it does not bound the agent that wrote it, the other MCP servers it talks
> to, or a Python or shell script. `sabline mcp` is an MCP server whose
> ceiling bounds what a model may ask *this* server for, and nothing more.
> Within a grant, a program may do anything the grant covers - it can write
> nonsense into the folder it may write to. And the budget is enforced by an
> interpreter in the program's own process, with the operating system
> holding it too, fully only on Linux ([the threat model](../THREAT_MODEL.md)).

**Last verified:** 2026-09-25. The Sabline examples run on every push; the
quoted warning is as the issue above records it on that date.

## The task, and one step past it

Tidy three reports: read each from `reports/`, write a copy to `out/`. The
script also leaves a note in a folder outside both, which nobody asked for.

<!-- file: examples/guides/tidy_reports.vel -->
```vel
// Tidies three reports: reads each from reports/, writes a copy to out/.
// Then, unasked, it leaves a note in a folder outside both.
fn main() uses io, fs {
    for name in ["a.txt", "b.txt", "c.txt"] {
        check read_file("reports/" + name) {
            ok text {
                write_file("out/" + name, upper(text))
                print("tidied " + name)
            }
            fail why {
                print("skipped " + name + ": " + why)
            }
        }
    }
    write_file("../notes/todo.txt", "tidied three reports\n")
}
```

`uses io, fs` is all the signature can say: files, in general. The budget
says which.

## One folder to read, one to write

```console
$ sabline examples/guides/tidy_reports.vel --allow io,fs:read:./reports,fs:write:./out
tidied a.txt
tidied b.txt
tidied c.txt
error[E313] 'write_file' reaches '../notes/todo.txt' (resolved: <your folder>/notes/todo.txt), which this run's fs grants do not cover
  --> examples/guides/tidy_reports.vel, line 15
```

The three reports are tidied; the note is refused, and the run ends there.
Every path is resolved - `..` and symbolic links included - before it is
compared with the grant, so a path cannot climb out of `./out` by spelling.
A read under a write-only grant, or a write under a read-only one, is refused
the same way.

## A number of operations

A grant can also say how many. Two file operations are not enough for three
reports:

```console
$ sabline examples/guides/tidy_reports.vel --allow io,fs:read:./reports@2,fs:write:./out
tidied a.txt
error[E315] 'read_file' is the 3rd fs operation, and this run allows 2
  --> examples/guides/tidy_reports.vel, line 5
```

Counts work on the network too: `net:api.example.com:443@100` is at most a
hundred requests to that host.

## When a model asks for the budget

Sabline's MCP server lets a model write and run Sabline, and the operator
sets the most any request may have. A model can ask for less, never more:

<!-- illustrative: starts a server that waits for an MCP client on stdin -->
```sh
sabline mcp --max-allow io,fs:read:./reports,fs:write:./out
```

A request for a budget wider than that ceiling is refused before anything
runs. [EMBEDDING.md](../EMBEDDING.md) says how the ceilings on each of
Sabline's doors - the MCP server, the HTTP door and the library - work.

## What to take from it

- "Everything or nothing" is a property of the tool, not of the task. Write
  down what the task needs - these folders, that host, about this many
  operations - and grant that.
- The budget is the operator's, not the program's: the program's own
  signature can only ask.
- For the whole agent, rather than the code it writes, the boundary has to
  be around the agent: an operating-system sandbox, a container, a VM.
  [The comparisons](compare-wasi.md) say where that design is stronger.
