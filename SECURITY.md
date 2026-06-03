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
