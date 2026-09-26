# Four notes, to send once the flagship page is live

The flagship - "We examined N real incidents and replayed M in Sabline" -
is written only once every catalogue entry is checked (`verified: true`),
so these wait for it. Each note is tied to something the person wrote, quoted from the page
itself (`plan/findability-research/people.md` has the links and dates),
says what Sabline does not do, and asks for nothing but a correction if they
see one. Use each person's own public channel as their site lists it; no
contact details are collected here. Rewrite in your own voice; keep them
this short.

## Andrew Nesbitt - on "Package Manager Sandboxing" (nesbitt.io, 2026-09-24)

> Hi Andrew - your Package Manager Sandboxing post sorts the fixes for
> install-time code into gating it, confining it, or replacing it "with data
> that is interpreted rather than executed". I've been building a narrow
> version of confining at the language level: Sabline, where a script's
> functions declare what they may touch and the person running it grants one
> folder or one host. It does nothing for npm or pip install scripts, and the
> replays of Shai-Hulud and Nx on this page say exactly where it stops:
> [flagship link]. If I've misread any of those incidents, I'd rather know.

## Seth Larson - on the Ultralytics analysis (blog.pypi.org, 2024-12-11)

> Hi Seth - your analysis of the Ultralytics compromise is the source for
> one entry in an incident catalogue I keep for Sabline, a language that
> refuses what a script was not granted. That entry is marked NOT COVERED:
> the attack was a workflow injection and a cache poisoning, which nothing
> in Sabline addresses, and the page says so rather than stretching a
> budget to fit. [link to the Ultralytics page]. If the summary misstates
> anything in your analysis, I'll correct it.

## tl;dr sec (Clint Gibler) - a reply to an issue

tl;dr sec has no submission route; each issue says "Just reply directly".
Reply to an issue that covers agent sandboxing or an incident on the
flagship:

> Hi Clint - in #281 you wrote of runtime guardrails and access controls for
> agents that "solutions are still quite nascent". In case it's useful for a
> future issue: Sabline is an open-source language where an agent's script
> declares what it may touch and the operator's budget is refused against at
> each operation, with OS confinement underneath on Linux. The comparisons
> open with where Deno, WASI and CaMeL are ahead of it, and the incident
> replays say what a budget stops and what it doesn't: [flagship link].

## Simon Willison - on "The lethal trifecta for AI agents" (simonwillison.net, 2025-06-16)

> Hi Simon - your lethal trifecta post says "The only way to stay safe there
> is to avoid that lethal trifecta combination entirely." I wrote a guide
> that applies that to one run of an agent-written script in Sabline: grant
> the read, withhold the network, and the steered send is refused
> [guide link]. It says first what it doesn't do - with both a read and a
> send granted it can't stop data moving between them, where CaMeL can. If
> I've represented your argument unfairly anywhere, I'd like to fix it.
