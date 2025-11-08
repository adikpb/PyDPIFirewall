# Deep Packet Inspection Firewall

A Python-based Deep Packet Inspection (DPI) firewall that inspects HTTP traffic using mitmproxy, applies rules-based filtering, and provides metrics via a FastAPI endpoint.

## Features

- **Deep Packet Inspection**: Inspects HTTP traffic using mitmproxy
- **Rule-based Filtering**: Block requests based on regex patterns in URL, headers, or body
- **Database Logging**: Stores all requests in SQLite database using SQLModel
- **Metrics API**: FastAPI endpoint to retrieve total and blocked request counts
- **Dynamic Rules**: Automatically reloads rules when `rules.json` changes using watchdog
- **Comprehensive Logging**: Logs all firewall events with appropriate log levels

## Installation

1. Install dependencies:

```bash
uv sync
```

2. (Optional) Edit `.env` to configure ports and other settings

## Configuration

### Environment Variables

- `FASTAPI_PORT`: Port for FastAPI metrics endpoint (default: 8000)
- `MITMPROXY_PORT`: Port for mitmproxy proxy server (default: 8080)
- `DB_PATH`: Path to SQLite database file (default: firewall.db)
- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)
- `RULES_FILE`: Path to rules JSON file (default: rules.json)

### Rules File Format

The `rules.json` file contains structured rules:

```json
{
  "rules": [
    {
      "pattern": "regex_pattern",
      "type": "url|header|body",
      "action": "block",
      "description": "Rule description"
    }
  ]
}
```

- `pattern`: Regular expression pattern to match
- `type`: Where to check - "url", "header", or "body"
- `action`: Currently only "block" is supported
- `description`: Human-readable description of the rule

## Usage

1. Start the firewall:

```bash
uv run -m backend.main
```

2. Configure your client to use the proxy:
   - Proxy host: `localhost`
   - Proxy port: `8080` (or your configured `MITMPROXY_PORT`)

3. Access metrics:

```bash
curl http://localhost:8000/metrics
```

4. Health check:

```bash
curl http://localhost:8000/health
```

## API Endpoints

### GET /metrics

Returns firewall metrics:

```json
{
  "total_requests": 100,
  "blocked_requests": 5
}
```

### GET /health

Returns health status:

```json
{
  "status": "healthy"
}
```

## Database Schema

The SQLite database stores request logs in the `requests` table:

- `id`: Primary key
- `url`: Request URL
- `blocked`: Boolean indicating if request was blocked
- `timestamp`: Timestamp of the request
- `headers`: Request headers (stored as string)
- `body`: Request body (stored as string)

## Notes

- Only HTTP traffic is inspected (HTTPS is not supported)
  > [!NOTE]
  > Unless certificate is trusted from mitm.it after connecting to proxy
- Blocked requests return HTTP 403 Forbidden with a custom message
- Rules are automatically reloaded when `rules.json` is modified
- The firewall runs mitmproxy and FastAPI in the same process

## Example

To test the firewall:

1. Start the firewall
2. Configure your browser to use `localhost:8080` as HTTP proxy
3. Visit a website
4. Check logs and metrics endpoint to see requests being processed
