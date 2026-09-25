# Measuring findability: a monthly checklist

Once a month, on or near the 25th, re-take the baseline in
[findability-baseline.md](findability-baseline.md) (2026-09-25) the same way,
and write the result as `findability-YYYY-MM.md` beside it. The point is to
compare like with like: the same queries, the same tool, the same reading
of the results.

## 1. The searches (about 40 minutes)

- [ ] With the same tool as the baseline (Claude Code's WebSearch; say so if
      another is used, and do not compare across tools), run each of the
      **30 phrasings** exactly as the baseline's "Query" line gives it, and
      the six name queries (`Sabline`, `Velaris`, `Sabline programming
      language`, `Velaris programming language`, `sabline.dev`,
      `site:sabline.dev`), and the three in Sabline's own terms.
- [ ] For each, record the top five and **the rank of any sabline.dev,
      sabline-lang or Sabline result in the list returned** (or "none").
- [ ] Note any new thing named Sabline or Velaris competing in the results.
- [ ] Where a search engine can be reached directly (Google, Bing,
      DuckDuckGo), repeat the name queries there too, and label them.

The number to watch is how many of the 30 phrasings return a Sabline page
at all - 0 on 2026-09-25 - and for which guide's phrasing first.

## 2. The AI assistants (once a browser is connected)

The baseline could not reach them: the Chrome extension was not connected,
ChatGPT and Perplexity answered a direct fetch with 403, and Google's AI
Mode gave a page with no answer. With the Claude in Chrome extension
connected, ask each of **ChatGPT, Claude, Perplexity and Google AI Mode**
these ten phrasings, verbatim, each in a new conversation, signed out where
the service allows it:

1. "[BUG] Claude loads my projects .env into its bash environment (!)"
2. "Is it possible to ensure that the agents don't get access to sensitive directories in the device such as ~/.ssh and ~/.gnupg?"
3. "I don't want it inadvertently deleting the wrong things or reading my SSH keys."
4. "Giving agents enough permission to be useful seems at odds with least-privilege."
5. "I shouldn't have to decide between giving a model access to everything I can access, or nothing."
6. "Installing will grant access to everything on your computer." (ask: "What can I do about an MCP extension that says this?")
7. "When declaring dependencies, you'd also declare the permissions of those dependencies. So a package like tinycolor would never need network or disk access."
8. "To me it's quite unexpected/scary that installing a package on my dev machine can execute arbitrary code before I ever have a chance to inspect the package"
9. "there's no reason an action like this ever needed network access."
10. "If your agent combines these three features, an attacker can easily trick it into accessing your private data and sending it to that attacker."

(Numbers 1, 9, 13, 15, 16, 19, 20, 21, 23 and 26 in the baseline.) Record
each answer **verbatim**, with the date, the assistant, the model it names,
and whether it was signed in. Mark whether Sabline is named, and whether
what it says about Sabline is right; a wrong description is worth fixing
at its source (the page it was drawn from).

## 3. The site and the listings (10 minutes)

- [ ] `python check_listings.py --github`: the description, homepage and
      topics on GitHub still match the one description.
- [ ] `curl -sI https://sabline.dev/sitemap.xml` and `/robots.txt` answer 200;
      `curl -sI https://velaris-lang.dev/` still answers 301 to sabline.dev
      (the monthly workflow's `check_urls.py` checks the card's old address
      too).
- [ ] The last few runs of `indexnow.yml` are green (a 403 means the key
      file and the key disagree).
- [ ] If the site is verified in Google Search Console and Bing Webmaster
      Tools (it is not yet; both need the owner's account), note pages
      indexed, the queries that brought impressions, and any the sitemap
      reports as not indexed.
- [ ] PyPI downloads for `sabline-lang` last month (pypistats), npm weekly
      downloads, GitHub stars, and the repository's traffic referrers
      (`gh api repos/gowrishankar-infra/sabline-lang/traffic/popular/referrers`,
      which keeps 14 days only).

## 4. What to do with it

- A guide whose phrasing still finds nothing after three months: check its
  title and description against how people wrote the phrasing, not how
  Sabline would put it.
- A phrasing whose results changed completely: re-read what now ranks; it
  may answer the question better than the guide does, and the guide
  should link it.
- Never: add keywords to a page for a crawler, hide text, or post about
  Sabline where it does not answer the question asked.
