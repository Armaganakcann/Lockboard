# Security policy

## Scope and limitations

Lockboard runs submitted JavaScript in a terminable browser Worker under a restrictive Content Security Policy and removes selected network/messaging APIs. This is defense in depth, **not a hostile-code security boundary or a general-purpose sandbox**. Candidate code can still consume CPU or memory before the Worker terminates.

Do not enter secrets or sensitive data into candidates. Use the project only in an isolated development environment with code you understand. The demo has no authentication, backend or persistent storage.

## Reporting a vulnerability

Please **do not publish weaponized payloads or exploitable details in a public issue**. Prefer GitHub's private vulnerability reporting feature if enabled for this repository. Otherwise, contact the maintainer privately through an existing verified contact method listed on their GitHub profile. If neither option is available, open a public issue describing the affected component and request a private contact channel, without including exploit details.

Provide a minimal reproduction, browser/version, affected behavior and expected outcome. No response-time SLA is promised for this volunteer-maintained project.

## Supported versions

Security fixes are considered for the latest code on the \`main\` branch only. Older commits and the superseded AIOS implementation are unsupported.
