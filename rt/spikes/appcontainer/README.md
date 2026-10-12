# The AppContainer spike

`plan/9.0.md`'s risk register, item 3: *the whole Windows half of M4 rests
on a claim nobody has tested - that a statically linked Rust binary can
start inside an AppContainer and still do its job, where `python.exe`
cannot.* This program is the measurement, run on 2026-10-12 on Windows 11
Pro 10.0.26200 (x64), Rust 1.97.1, as an ordinary user. It is not product
code and is not a member of the `sabline-rt` workspace: it has no
dependencies, no test, and nothing builds it but

    cargo run --release --manifest-path rt/spikes/appcontainer/Cargo.toml

It creates an AppContainer profile of its own, grants the container's SID
directories by adding ACEs at run time, starts copies of itself inside the
container under seven conditions, and has each copy attempt and report the
attempts the plan names. Then it puts every DACL back and deletes the
profile. [recorded.txt](recorded.txt) is its output, with the user's
directories written as `%TEMP%`, `%LOCALAPPDATA%` and `%USERPROFILE%`.

## What it had to show, and what it showed

| The plan asks | Measured |
|---|---|
| reads held to the granted directory | **yes**: a directory given one ACE for the container's SID (read, execute) is read and listed; a sibling directory without one, a file of the user's (`%USERPROFILE%\.gitconfig`) and the program's own build directory are refused, *Access is denied* |
| the network refused without the capability | **yes**: TCP to an address outside the machine fails at once with WSAEACCES (10013) when the container holds no capability, and connects with `internetClient` (S-1-15-3-1) |
| standard input and output still working | **yes**: a line written to the child's inherited standard input is read, and every line it writes reaches the parent |
| a granted directory reachable by adding one ACE at run time, not by asking a user to relabel anything | **yes**, and for writes too: an ACE granting read and write is enough to make, overwrite and remove files in the directory, on `C:` and on `D:`, with no integrity label - a low label is not needed |

So the spike **succeeded**, in a day of its five-day box, and M4's Windows
half goes ahead as planned.

## What else it found, which the design has to answer

- **The executable needs no ACE to start.** A copy started from where it
  was built, with nothing granted anywhere, runs (case 1): the image is
  mapped by the process that creates it. It cannot *read* its own file -
  which a Rust binary does not need to - unless it is given an ACE.
- **Starting a process is not held by an AppContainer.** `cmd /c exit 0`
  ran from inside in every case. The job object that holds Python's run to
  one process is still needed beside it.
- **Loopback is never reachable from inside, even with `internetClient`**
  (cases 1 to 6: TCP to 127.0.0.1 times out). Windows isolates an
  AppContainer from the loopback address unless an administrator exempts
  it. A run that relays its network calls to its host, as sabline-rt does
  until the network is ported, does not care; a sabline-rt that makes
  connections itself cannot reach a granted `net:localhost` from inside a
  container, and has to say so rather than be refused at the call.
- **`internetClient` admits every host.** The capability is not per host,
  so a run under `net:HOST` is held by the language for the host, as on
  Linux and macOS, and its level is partial.
- **What a container writes to by default is its own.** The child's
  temporary directory is `%LOCALAPPDATA%\Packages\<profile>\AC\Temp`, made
  with the profile and removed with it, and the system's files that every
  container may read (`C:\Windows\win.ini`) stay readable.
- **The ACEs live on the user's own directories** until they are taken
  back. A run that is killed before it puts them back leaves an ACE naming
  the SID of a profile that is gone; a profile name that is new for each
  run makes that SID one nothing can hold again, but the ACE stays until
  something removes it. The design has to say who does.
