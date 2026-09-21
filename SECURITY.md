# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (main) | Yes |
| older | No |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security reports.

Preferred:

1. Use [GitHub Private Vulnerability Reporting](https://github.com/StormForgeVentures/pifang/security/advisories/new) on this repository (enable in repo settings if needed), or
2. Email **hello@stormforgeventures.com** with a description, impact, and repro steps.

We aim to acknowledge reports within 7 days and to provide a remediation timeline after triage.

## Scope notes

Pifang is a local CLI. Typical concerns include path handling, unsafe subprocess arguments to ffmpeg/engines, and dependency supply chain. It does not host multi-tenant cloud services.
