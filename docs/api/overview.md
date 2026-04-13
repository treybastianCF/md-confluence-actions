---
confluence_id: '4351721583'
---

# API Overview

This section covers the REST API for this project.

## Base URL

All API requests are made to:

```
https://api.example.com/v1
```

## Authentication

Requests must include an `Authorization` header with a bearer token:

```
Authorization: Bearer <your-token>
```

## Response Format

All responses are JSON with the following envelope:

- `data` — the response payload
- `error` — present only on failure, contains `code` and `message`
- `meta` — pagination info where applicable