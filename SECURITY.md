# Security Policy

## Scope

`scgraph` is an analysis tool. It reads public advisory and dependency data and produces
reports. It does not execute dependency code, and it makes no network calls during
graph construction. The main security considerations are:

- The evaluation and acquisition scripts run `git clone`, `curl` or `aria2c`, `tar`,
  and (in the osv-scanner comparison) a downloaded binary. These run only when you
  invoke them, and they hold no credentials.
- `scripts/fetch_artifacts.py` downloads release assets and checks them against a
  recorded sha256 once a release exists.

## Reporting a vulnerability

Please report privately through GitHub's
[private vulnerability reporting](https://github.com/FareedKhan-dev/ai-graph-engineering-supplychain/security/advisories/new)
rather than opening a public issue.

Include the version, a description, and a reproduction if you have one. You can expect an
acknowledgement within a few days and a fix or a mitigation plan for confirmed issues.

## Supported versions

The latest tagged release receives fixes. This project follows semantic versioning.
