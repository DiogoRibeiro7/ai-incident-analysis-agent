# Security Policy

## Supported Versions

This project is currently pre-`v1.0.0`.

- `main`: supported
- tagged releases older than the latest minor line: best effort only

Security fixes are prioritized on active development branches and then included in the next release.

## Reporting a Vulnerability

Please do **not** open public GitHub issues for suspected vulnerabilities.

Report privately by email:

- `diogo.ribeiro.dev+security@proton.me`

Include:

- affected component or file path
- reproduction steps or proof of concept
- impact assessment (confidentiality, integrity, availability)
- suggested remediation if available

## Response Expectations

- Initial acknowledgment: within **72 hours**
- Triage decision and severity classification: within **7 days**
- Remediation plan or workaround: as soon as practical based on severity

If the report is accepted, maintainers will coordinate disclosure timing and credit the reporter (if desired).

## Scope Notes

In scope:

- source code in this repository
- CI/CD workflow configuration
- default runtime configuration and documentation

Out of scope:

- vulnerabilities in third-party services outside repository control
- unsupported local environment customizations not documented by the project
