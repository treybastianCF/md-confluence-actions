# Authentication

This guide explains how to authenticate with the API.

## API Tokens

API tokens are the recommended authentication method. They are:

- **Scoped** — each token can be limited to specific permissions
- **Revocable** — invalidate a token without changing your password
- **Auditable** — token usage is logged separately from user sessions

## Generating a Token

1. Log in to your account at `https://app.example.com`
2. Navigate to **Settings → API Tokens**
3. Click **New Token**
4. Give it a descriptive name and select the required scopes
5. Copy the token — **it will not be shown again**

## Using the Token

Include the token in the `Authorization` header of every request:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## Token Scopes

| Scope | Access |
|-------|--------|
| `read:users` | Read user records |
| `write:users` | Create and modify users |
| `read:items` | Read item records |
| `write:items` | Create and modify items |
| `admin` | Full access (use sparingly) |

## Security Best Practices

- **Never commit tokens** to version control
- Store tokens in environment variables or a secrets manager
- Use the minimum scope required for your use case
- Rotate tokens periodically and immediately if compromised
