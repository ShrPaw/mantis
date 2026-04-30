# SECURITY_CHECK.md — MANTIS Repository

**Date:** 2026-04-30  
**Scanner:** Manual grep + git history analysis

---

## Files Scanned

All source files (`.py`, `.ts`, `.tsx`, `.js`, `.json`, `.yaml`, `.yml`, `.sh`, `.md`) excluding:
- `.git/` directory
- `node_modules/`
- `venv/`

## Findings

| Check | Status |
|-------|--------|
| GitHub tokens (`ghp_*`) in source | ✅ NONE |
| API keys in source | ✅ NONE |
| Hardcoded passwords | ✅ NONE |
| `.env` files committed | ✅ NONE |
| `.env` in `.gitignore` | ✅ YES (`*.env` + `.env`) |
| `data/` gitignored | ✅ YES |
| `*.jsonl` gitignored | ✅ YES |
| `*.log` gitignored | ✅ YES |
| Secrets in git history | ✅ NONE |

## .gitignore Coverage

```
backend/venv/          — Python venv
frontend/node_modules/ — npm deps
__pycache__/           — Python bytecode
*.pyc                  — Python bytecode
frontend/dist/         — Build output
backend/data/          — Runtime data
data/                  — Runtime data
backend/mantis_events.log — Logs
backend/nohup.out      — Process output
*.jsonl                — Event logs
.env                   — Environment vars
.env.*                 — Environment variants
*.log                  — All logs
nohup.out              — Process output
*.tar.gz               — Archives
```

**Assessment:** `.gitignore` is comprehensive. Runtime data, logs, and environment files are properly excluded.

## ⚠️ User-Supplied Credential

A GitHub Personal Access Token (`ghp_...`) was provided in chat for repository access. This token:
- Was used only for `git clone`
- Is NOT stored in any file in the repository
- **Should be rotated after this session** as it was transmitted in plaintext

## Final Security Status

**✅ PASS — No secrets found. Repository is clean.**

Recommendation: Rotate the GitHub PAT used for clone access.
