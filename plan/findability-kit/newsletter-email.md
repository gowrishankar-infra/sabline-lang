# Newsletters

Routes read 2026-09-25 (`plan/findability-research/venues.md`). Rewrite in
your own words before sending; none of these venues states a rule about
text a model wrote, but a note from a person reads as one.

## Email: Console (hello@console.dev) and Help Net Security (press@helpnetsecurity.com)

Console takes tools by email and features "Interesting tools" weekly (its
betas slot is pre-1.0 only, so not that one); Help Net Security's monthly
newsletter covers open-source security tools and takes pitches at the press
address. One email, sent to each separately:

> **Subject:** Sabline - run code an AI wrote without handing it everything you can reach
>
> Hello,
>
> I build Sabline, an open-source (MIT) language for the scripts an AI agent
> writes. Each function declares what it may touch - files, hosts,
> environment variables, the clock, Python modules - and the person running
> it grants one folder, one host or a number of calls. The runtime refuses
> anything else at the moment it is tried, and the program cannot catch the
> refusal. `pip install sabline-lang`, then `sabline demo`, shows it in
> under a minute with no network: a script that reads `./.env` and posts it
> is refused, then the same task runs inside a budget.
>
> What it does not do, since you will ask: it bounds programs written in
> Sabline, not Python or shell; the interpreter enforcing the budget runs in
> the program's own process, with the operating system holding the same
> budget underneath - fully on Linux, partly on macOS and Windows; and it
> does not track data from a granted read to a granted send.
>
> Five guides start from how people describe the problem (an agent reading
> `.env`, a package that did not need the network):
> https://sabline.dev/guide-network-access.html. The comparisons with Deno,
> WASI, CaMeL and AILANG open with where each is ahead of Sabline:
> https://sabline.dev/compare-deno.html.
>
> Repository: https://github.com/gowrishankar-infra/sabline-lang
>
> Thanks for reading,
> [your name]

## PyCoder's Weekly: the public form

<https://pycoders.com/submissions> leads to a Google Form. For a project the
description field is not used, so the title must say what it does.

- **URL:** https://github.com/gowrishankar-infra/sabline-lang
- **Title / Headline** (at most 220 characters; this is 149):
  `Sabline: a language for AI-written scripts where each function declares what it may touch and the runtime refuses anything the operator did not grant`
- **Description / Summary** (at most 450 characters; this is 357):
  `Sabline (MIT, pip install sabline-lang) runs code a model wrote under a budget the operator writes: one folder, one host, a set of Python modules, a number of calls. Functions declare their effects in their signatures, contracts go to Z3, and any operation outside the budget is refused when it is attempted. It also ships an MCP server and a GitHub Action.`

## tl;dr sec: a reply, not a pitch

There is no submission route; each issue ends "Just reply directly". If you
subscribe, a reply to an issue that touches agent sandboxing is the one way
in - see the tl;dr sec note in [notes-to-people.md](notes-to-people.md).
Sponsorship is a separate route and buys no editorial coverage.
