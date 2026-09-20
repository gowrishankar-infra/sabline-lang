# Getting Sabline into the frameworks

Three ready-to-submit integrations, in the order to submit them.

Both framework tools call plain `sabline.run`, one process per
call, and not `sabline.Pool`. A crew's tool is not called often
enough for a pool to pay for itself, and one process per call is
easier for a reviewer to reason about. EMBEDDING.md says when a
pool is worth it.

## 1. CrewAI  (`crewai/`)  — submit first

`crewai-tools` accepts community tools by pull request.

1. Fork `github.com/crewAIInc/crewAI-tools`
2. Copy `crewai/sabline_tool.py` to their tools directory following
   their layout, and `test_sabline_tool.py` beside their tests
3. Add `sabline-lang` to their optional dependencies
4. Open the PR with the text in `PR_CREWAI.md`

Reply to review comments within a day. That matters more than the code.

## 2. MCP registry  (`mcp_registry/`)  — a form, not a PR

Every MCP client - Claude, Cursor, VS Code, the OpenAI Agents SDK -
reads the registry at registry.modelcontextprotocol.io. Submit
`server.json` through their publisher CLI (`mcp-publisher`), which
verifies you own the GitHub namespace. Highest reach of the three.

## 3. LangChain  (`langchain_sabline/`)  — after PyPI

LangChain lists partner packages rather than merging tools.

1. Publish: `cd langchain_sabline && python -m build && twine upload dist/*`
2. Open a PR to `langchain-ai/langchain` adding a page under
   `docs/docs/integrations/tools/sabline.ipynb` - copy an existing
   tool page's shape, they are strict about it
3. They check the package installs from PyPI, so publish first

## What gets merged

A real test that runs in their CI. A description that explains the
problem, not the product. No marketing words. And a maintainer who
answers review comments quickly.
