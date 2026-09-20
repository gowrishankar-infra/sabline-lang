# The last release under the old name

Velaris was renamed Sabline in 8.6.0 (CHANGELOG, [docs/renamed.md](../../docs/renamed.md)).

Nothing published under the old name is deleted, yanked or moved: an
install pinned to `velaris-lang==8.5.0` must go on resolving to the same
file, with the same digest and the same signature. That is the rule this
project kept when 3.4 was not retagged and when 6.0.0 was yanked rather
than deleted, and a rename is not a reason to break it.

But somebody whose requirements say `velaris-lang` with no pin, or who runs
`npm install velaris-lang`, should learn that the project moved rather than
sit on 8.5.0 for ever. So each old name gets **one last release, 8.6.0**,
which holds no code of its own: it depends on `sabline-lang`, and it says
on its page and on install that the project is now Sabline.

| Name | What the last release is |
|---|---|
| PyPI `velaris-lang` 8.6.0 | [pypi/velaris-lang](pypi/velaris-lang) - depends on `sabline-lang>=8.6.0`; its description is the rename notice |
| npm `velaris-lang` 8.6.0 | [npm/velaris-lang](npm/velaris-lang) - depends on `sabline-lang`, re-exports it, and prints the notice on install. Then `npm deprecate` |
| VS Code `gowrishankar-infra.velaris` 8.6.0 | [vscode](vscode) - a final version whose README says to install `gowrishankar-infra.sabline` |
| MCP registry `io.github.gowrishankar-infra/velaris` | nothing is published to it again; it is marked deprecated, which is the registry's own way of saying a server has moved |

The `velaris` command and `import velaris` are **not** here. Those are in
sabline-lang itself, which installs both names for one major version
(STABILITY.md, *Deprecations in force*), so somebody who upgrades through
this stub gets a working `velaris` command from the new package.

## The one that is a real break

A VS Code Marketplace extension id cannot be renamed, and an extension
cannot install another. Anyone who has `gowrishankar-infra.velaris`
installed has to install `gowrishankar-infra.sabline` themselves. The final
version of the old extension is how they find out: its README says so, and
it no longer contributes the `velaris` language, so it cannot fight the new
one over a `.vel` file.

## Publishing them

Each needs a credential this repository does not keep, and each is a
one-off. MAINTENANCE.md has the checklist; in short:

**PyPI.** `velaris-lang` already exists, and its trusted publisher names
this repository under its old name. Renaming the repository changes the
OIDC claim, so that publisher has to be edited to say `sabline-lang` before
anything can be published to `velaris-lang` again:

    pypi.org -> velaris-lang -> Manage -> Publishing
      repository: sabline-lang     (was velaris-lang)
      workflow:   farewell.yml     (was release.yml)
      environment: placeholders

Then `gh workflow run farewell.yml`.

**npm.** The same, at npmjs.com -> velaris-lang -> Settings -> Trusted
publisher. Then the workflow publishes it, and afterwards, as the package
owner:

    npm deprecate velaris-lang "renamed: this project is now sabline-lang (https://sabline.dev)"

**VS Code.** From [vscode](vscode), with the `VSCE_TOKEN` that publishes
the extension:

    npx @vscode/vsce publish --pat "$VSCE_TOKEN"

**The MCP registry.** The old server keeps every version it published;
nothing is deleted. Mark it deprecated so a client that lists servers sees
that it has moved (RELEASING.md, *Yank a release*):

    mcp-publisher login github
    mcp-publisher status --status deprecated \
        io.github.gowrishankar-infra/velaris 8.5.0

The new server, `io.github.gowrishankar-infra/sabline`, is published by the
release workflow like any other version - by GitHub OIDC, with no token
stored - as soon as PyPI and npm serve `sabline-lang` naming it.

Nothing here is published by the release workflow. A release publishes the
current names and nothing else; these four are run once, by hand, and then
never again.
