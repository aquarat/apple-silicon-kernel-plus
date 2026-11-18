# Contributing

Changes come as pull requests against `main`; the steps, versions and
commit rules are in [docs/release-process.md](docs/release-process.md) and
[docs/maintainer-guide.md](docs/maintainer-guide.md).

## Every patch comes with a document

A pull request that adds a patch (kernel, AVD, Mesa or any other package),
or that changes what a patch does, also adds or updates its document in
`docs/` and its row in [docs/README.md](docs/README.md). The pull request
description is not enough: it is not in the repository, and the next
rebase or reviewer needs the rationale where the patch is.

One document per patch or per tightly related series, named by topic (not
by patch number), covering:

- what it does;
- why: the problem and the evidence;
- the design and the alternatives considered;
- how it was tested, with the measured results;
- known limitations and open items;
- which SoCs or hardware it applies to;
- upstream status and provenance (whose work it is, what it was written
  from; consistent with [LICENSING.md](LICENSING.md));
- the pull request(s).

Results that arrive after the pull request (a hardware run, a review
round) go into the document too.

Renumbering patches (a rebase) only needs the file names in
`docs/README.md` updated.

## Public repository

Describe machines generically ("an M1 Max MacBook Pro"), not by host name.
No IP addresses, host names, personal paths or e-mail addresses other than
the GitHub noreply address, and no Apple firmware or data taken from
Apple's files.
