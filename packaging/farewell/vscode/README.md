# Renamed: install **Sabline**

This extension is no longer developed. The project it supports was called
Velaris until 8.6.0; the name belongs to an unrelated company in the same
market (velaris.io), so it was given up.

## Install this instead

**[Sabline](https://marketplace.visualstudio.com/items?itemName=gowrishankar-infra.sabline)**
— `gowrishankar-infra.sabline`, or in VS Code: Extensions, then search for
*Sabline*.

It is the same extension under the new name, kept up to date: syntax
highlighting for `.vel`, and live errors and proofs from the real compiler.

## Why not just rename this one

A Marketplace extension id cannot be renamed, and an extension cannot
install another. This is the only way to tell you, and this is its last
version. It no longer contributes a language, so it will not fight the new
extension over a `.vel` file — you can uninstall it whenever you like.

## Nothing else has to change

The `.vel` extension is unchanged, and the compiler still answers to the
old names for one major version: the `velaris` command, `import velaris`,
`VELARIS_*`, a committed `velaris.capabilities`. See
<https://sabline.dev/renamed.html>.
