# Quickstart Guide

Get up and running in under 5 minutes.

## Prerequisites

- Python 3.10 or higher
- A valid API token

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/your-repo.git
cd your-repo

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set the following environment variables:

```bash
export API_URL="https://api.example.com/v1"
export API_TOKEN="your-token-here"
```

## Your First Request

```python
import requests
import os

headers = {"Authorization": f"Bearer {os.environ['API_TOKEN']}"}
response = requests.get(f"{os.environ['API_URL']}/users", headers=headers)
print(response.json())
```

## Next Steps

1. Read the [API Overview](docs/api/overview.md) to understand the response format
2. Browse the full [Endpoints Reference](docs/api/endpoints.md)
3. Learn about [Authentication](docs/guides/authentication.md)
