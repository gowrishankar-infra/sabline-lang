# Show HN: facts and a checklist, not a draft

**Why there is no drafted title or comment.** Hacker News's guidelines say
"Don't post generated text or AI-edited text. HN is for conversation between
humans" (<https://news.ycombinator.com/newsguidelines.html>), and the tips
`showhn.html` links (dang, edited 2026-03-28) say "Write your text by hand.
Don't use an LLM to generate any of it (not even a tiny bit, including to
edit or spruce it up)." A title or a first comment written here and pasted
there would break the venue's own rule. So this file gives the facts to
draw on and the rules to check against; the words have to be yours.

Also in force (read 2026-09-25): Show HNs are "temporarily" restricted for
accounts new to the site (a snapshot of <https://news.ycombinator.com/showlim>
of 2026-05-12); an account with little history there may be refused. Neither
Sabline nor Velaris has ever been on Hacker News (an exact search, 2026-09-25).

## The rules to check your post against

From <https://news.ycombinator.com/showhn.html> and the guidelines:

- The title begins "Show HN:". No uppercase for emphasis, no exclamation
  marks, no "the best", no site name, nothing editorialised.
- "Show HN is for something you've made that other people can play with" -
  the playground (<https://sabline.dev/playground.html>) needs no sign-up,
  and `pip install sabline-lang` then `sabline demo` works offline.
- Say how and why you built it, and what is different about it, in plain
  words; "drop any language that sounds like marketing".
- No asking anyone to upvote or comment; no booster comments; don't delete
  and repost; don't have a username that is the project's name.

## Facts you can draw on

Every one of these is checkable in the repository or on sabline.dev:

- What it is: a small language for scripts a model writes. A function's
  signature declares its effects (io, env, fs, net, clock, rand, ffi); the
  person running it grants a budget - `--allow io,fs:read:./data,net:api.example.com:443`,
  counts like `@100` - and the runtime refuses anything outside it at the
  operation. The refusal cannot be caught.
- One command shows it: `sabline demo` writes an agent-style script that
  reads `./.env` and posts it, runs it with no budget (refused, E310), then
  the same task inside a budget.
- What it does not do: it bounds programs written in Sabline, not Python or
  shell; it is not a security boundary by itself (an interpreter in the
  program's process); the OS holds the same budget underneath fully on
  Linux (Landlock, seccomp) and partly on macOS and Windows; it does not
  stop data moving from a granted read to a granted send (CaMeL does,
  per value).
- Where it loses, measured: <https://sabline.dev/competitors.html> - Deno is
  ahead on 15 of 102 rows, and each comparison page leads with its losses.
- The incident replays, if the flagship is live by then (it is held back
  until every entry has been checked by a person).
- The history: renamed from Velaris in 8.6.0 because velaris.io is an
  unrelated company in the same market.
- You are one maintainer; say so, and say you are around to answer.

## What people will ask - have the answers ready

- "Why a new language and not a sandbox?" - the guides' "What this does not
  do" boxes, and the comparison with WASI, answer it without overclaiming.
- "Would this have stopped Shai-Hulud / tj-actions?" - no: those ran in npm
  and GitHub Actions. The replays are the shape of the attack, written in
  Sabline; the flagship says so first.
- "How is this different from AILANG?" - <https://sabline.dev/compare-ailang.html>.
