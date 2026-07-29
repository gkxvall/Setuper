# Security Policy

## Supported versions

Setuper has not published a stable release yet. Security fixes are currently
made on the default branch as part of development toward v1.0.0. This policy
will list supported release lines before the first public release.

## Reporting a vulnerability

Do not report suspected vulnerabilities in a public issue, discussion, pull
request, or commit.

Email [devwithvall@gmail.com](mailto:devwithvall@gmail.com) with a subject that
starts with `[Setuper Security]`. Include, when possible:

- the affected version or commit;
- the operating system and Python version;
- a minimal reproduction;
- the expected and observed behavior;
- the potential impact; and
- any suggested mitigation.

Do not send real credentials, private keys, tokens, personal data, or other
unnecessary secrets. Use redacted examples and explain how maintainers can
generate safe test data.

Maintainers will review the report privately, validate the issue, coordinate a
fix and disclosure when appropriate, and credit reporters who want attribution.
Response and remediation time depend on severity and maintainer availability.

## Scope

Reports about command execution, trust bypasses, secret disclosure, process
ownership, manifest validation, plugin isolation, browser privacy, and package
integrity are especially valuable. Reports about third-party applications or
services should be sent to their maintainers unless Setuper caused or amplified
the issue.
