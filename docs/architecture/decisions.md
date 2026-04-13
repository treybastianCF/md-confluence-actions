---
confluence_id: '4352540674'
---

# Architecture Decision Records

This document tracks significant architecture decisions for the project.

---

## ADR-001: REST over GraphQL

**Status:** Accepted

**Context:** We needed to choose an API style for the public-facing interface.

**Decision:** Use REST with JSON over GraphQL.

> REST is simpler to consume for the majority of our clients, easier to cache at the HTTP layer, and has better tooling support for documentation generation.

**Consequences:**
- Simpler onboarding for API consumers
- Some over-fetching in list endpoints (acceptable for now)
- GraphQL can be added later for power users if needed

---

## ADR-002: Python for Tooling Scripts

**Status:** Accepted

**Context:** We needed a language for internal tooling, CI scripts, and automation.

**Decision:** Use Python 3.10+ for all tooling scripts.

> Python has strong library support for HTTP, data processing, and cloud SDKs. The team has more Python experience than Node.js for scripting tasks.

**Consequences:**
- Consistent runtime across all scripts
- `requirements.txt` must be maintained for each script directory
- Scripts should target Python 3.10+ to use modern type hint syntax

---

## ADR-003: GitHub Actions for CI/CD

**Status:** Accepted

**Context:** We needed a CI/CD platform that integrates with our GitHub-hosted source code.

**Decision:** Use GitHub Actions exclusively for CI, CD, and automation workflows.

> Tight GitHub integration eliminates credential overhead. The free tier covers our current usage. Reusable workflows reduce duplication across repos.

**Consequences:**
- No external CI platform to maintain
- Workflows are version-controlled alongside code
- Vendor lock-in to GitHub (acceptable given existing commitment)