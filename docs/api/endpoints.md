---
confluence_id: '4352049218'
---

# API Endpoints

## Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | List all users |
| GET | `/users/{id}` | Get a user by ID |
| POST | `/users` | Create a new user |
| PUT | `/users/{id}` | Update a user |
| DELETE | `/users/{id}` | Delete a user |
| GET | `/items` | List all items |
| GET | `/items/{id}` | Get an item by ID |
| POST | `/items` | Create a new item |

## Rate Limits

| Tier | Requests per minute |
|------|---------------------|
| Free | 60 |
| Pro | 600 |
| Enterprise | Unlimited |

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad request — check your payload |
| 401 | Unauthorized — invalid or missing token |
| 404 | Not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |