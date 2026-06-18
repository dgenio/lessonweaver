# Security Policy

lessonweaver is an early-stage (alpha) project. We take security and privacy
seriously because the tool processes agent execution traces, which may contain
sensitive content.

## Supported versions

lessonweaver has not yet been published to PyPI; `0.2.x` is the current
(pre-release) development line. Until a `1.0.0` release, only the latest version
receives fixes.

| Version | Supported |
| --- | --- |
| 0.2.x (current) | :white_check_mark: |
| < 0.2 | :x: |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/dgenio/lessonweaver/security/advisories/new)
("Report a vulnerability" on the repository's **Security** tab). If that is
unavailable, contact the maintainer [@dgenio](https://github.com/dgenio).

When reporting, please include:

- a description of the issue and its impact;
- steps to reproduce (a minimal trace or command is ideal);
- any known mitigations.

We aim to acknowledge a report within a few business days.

## Scope and expectations

- `SimpleRedactor` is a **best-effort** safety net before export, not a
  compliance-grade privacy control. Do not rely on it to scrub regulated data.
- The core performs no network or LLM calls; report any behavior that violates
  that invariant as a security concern.
- Never include real credentials, tokens, or personal data in issues, traces,
  examples, or tests.

## Supply chain

lessonweaver is designed with zero runtime dependencies; optional developer
tools live in the `dev` extra and are used for tests, linting, typing, builds,
and release checks.

Releases use PyPI Trusted Publishing through the GitHub Actions publish workflow.
That workflow requests only `contents: read` and `id-token: write`, builds the
distribution from the release tag, and publishes with PyPI attestations enabled.
After a release is live, verify the package on the PyPI project page by checking
that the uploaded distribution includes an index-hosted attestation for the
matching GitHub release workflow run.

Repository workflows pin third-party GitHub Actions by full commit SHA with a
version comment next to each reference. Dependabot is configured to propose
weekly updates for GitHub Actions and Python developer dependencies, and the
OpenSSF Scorecard workflow runs on a schedule to surface supply-chain drift.
