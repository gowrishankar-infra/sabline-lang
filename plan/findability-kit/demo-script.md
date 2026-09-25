# Demo: four minutes, every command real

For a screen recording. Every command below is in the repository and runs
offline; the refusals are the ones the guides show and CI re-runs. Record in
a fresh folder with `pip install sabline-lang` done beforehand. Speak in your
own words - the lines under "Say" are what to cover, not a script to read.

## 0:00 - the problem (20 s)

Show: the guide
<https://sabline.dev/guide-secrets-env.html>, its opening quote on screen.

Say: an agent writes a script; the script runs with everything you can
reach - your `.env`, your SSH keys, any host. The question people keep
asking is why it needs any of that.

## 0:20 - one command (70 s)

```sh
sabline demo
```

Show: the first run refused - `error[E310] 'read_file' needs the 'fs'
effect, which this run does not allow (it allows: io)` - then the same task
inside a budget, then the difference between the two receipts.

Say: no budget given means the console and nothing else; the refusal comes
at the call, before anything is read; the program cannot catch it.

## 1:30 - one host, not the network (45 s)

```sh
sabline examples/guides/changed_files.vel --allow io,net:api.github.com:443
```

Show: the files listed, then `error[E314] 'post' reaches host
'collector.example.net', which this run does not allow`.

Say: this is the shape of the tj-actions compromise - a tool that lists
files, and a send to a host of its own. Grant the one host the task needs.

## 2:15 - before it runs (35 s)

```sh
sabline audit examples/guides/report.vel
sabline check examples/guides/tidy_helper.vel
```

Show: the audit's "WHAT IT CAN TOUCH" and "reached by"; then the helper
that says it only formats text refused with E300 before anything runs.

## 2:50 - a careless budget still keeps `.env` (35 s)

```sh
sabline examples/guides/report_config.vel --allow io,fs,net
```

Show: `error[E318] 'read_file' reaches './.env' ... a documented credential
location`.

Say: every file and the whole network granted, and a plain read of `.env`
is still refused; a key read as a Secret cannot be printed or sent.

## 3:25 - what it does not do (35 s)

Show: the "What this does not do" box of any guide, then
<https://sabline.dev/compare-camel.html>.

Say: it bounds programs written in Sabline, not your agent's shell; the
interpreter enforcing it runs in-process, with the OS holding the budget
fully only on Linux; and a granted read plus a granted send can still move
ordinary data - CaMeL tracks that per value, and is ahead there.

## 4:00 - where to go (10 s)

Show: <https://sabline.dev/>, the guides and the playground link.
