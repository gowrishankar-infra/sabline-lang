---
slug: xz-utils-backdoor
title: The xz-utils backdoor, CVE-2024-3094
date: 2024-03-29
lane: supply-chain
verdict: NOT COVERED
budget_line: none
verified: false
---

## What happened

On 29 March 2024 Andres Freund posted to the oss-security list: "After
observing a few odd symptoms around liblzma (part of the xz package) on
Debian sid installations over the last weeks (logins with ssh taking a lot
of CPU, valgrind errors) I figured out the answer: The upstream xz
repository and the xz tarballs have been backdoored." Versions 5.6.0 and
5.6.1 carried it. It activated during a Debian or RPM package build on
x86-64 Linux with gcc and the GNU linker, and interfered with sshd along
liblzma's dependency chain: openssh does not use liblzma itself, but Debian
and several other distributions patch it to link libsystemd, which depends on
liblzma. It redirected sshd's `RSA_public_decrypt` to its own code, so that
public-key authentication could be subverted.

## Sources

- [backdoor in upstream xz/liblzma leading to ssh server compromise](https://www.openwall.com/lists/oss-security/2024/03/29/4) - Andres Freund's original oss-security post, 29 March 2024, which is the public disclosure.
- [CVE-2024-3094](https://nvd.nist.gov/vuln/detail/CVE-2024-3094) - the CVE record.

## The shape, in Sabline

Code was added to an artefact during the build that produced it, and the
artefact was native. Nothing Sabline has addresses that shape. A budget
bounds what a running Sabline program may do; it is not a check on how a
binary was produced, and a compiled extension has, as THREAT_MODEL.md puts
it, "no source to read and whose behaviour a budget does not constrain any
more than it constrains Python".

This is the entry to read if you want the limit stated at its widest.
Sabline is itself a Python package built by a pipeline, signed, and
published to PyPI and npm; an attack of exactly this shape against that
pipeline would not be caught by anything in this repository, and
PROVENANCE.md's attestations would attest to the backdoored bytes as
faithfully as to any others. `sabline audit`'s `ffi_native` field reports
where a granted module ships a compiled extension, and it is deliberately
never allowed to say `false`.

## What this does not cover

All of it. Sabline bounds what a Sabline program does at run time and has
nothing to say about how any artefact - including its own - was built.
