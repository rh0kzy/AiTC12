# Backend

This backend exposes a simple Flask server that wraps the `ai` package's `AgentManager`.

Run locally:

```bash
python backend/server.py
```

The server listens on `http://127.0.0.1:5000/process_ticket` and accepts JSON POST requests:

```json
{ "ticket": "Your ticket text here" }
```

The frontend is configured to call `http://localhost:5000/process_ticket` by default.
