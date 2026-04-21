# Production deployment notes

This project is a Flask + Flask-SocketIO app (single-file `app.py`) with a SQLite database in `instance/`.

## Environment

- `SECRET_KEY` (required): strong random value.
- `DEBUG` (optional): set `DEBUG=1` to enable debug; leave unset/`0` in production.
- `PORT` (optional): defaults to `5000` inside the container/process.

Optional scheduled backups:

- `BACKUP_INTERVAL_MINUTES` (optional): set to a positive integer to enable periodic DB backups.
- `BACKUP_KEEP` (optional): keep newest N backups (default is to keep all).

## Run with Gunicorn (recommended)

Flask-SocketIO requires an async worker to support WebSockets.

Eventlet:

```bash
pip install -r requirements.txt
pip install gunicorn eventlet

export SECRET_KEY='...'
export DEBUG=0
export PORT=5000

gunicorn -w 1 -k eventlet -b 0.0.0.0:${PORT} app:app
```

Gevent (alternative):

```bash
pip install -r requirements.txt
pip install gunicorn gevent gevent-websocket

gunicorn -w 1 -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -b 0.0.0.0:${PORT} app:app
```

Notes:
- Use `-w 1` unless you add a shared Socket.IO message queue (multiple workers need a broker).
- Ensure `instance/` is writable and persisted (bind mount / volume).

## Nginx reverse proxy (HTTPS + WebSockets)

Minimal server block (adjust domain/certs/ports):

```nginx
server {
  listen 443 ssl;
  server_name example.com;

  ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

  client_max_body_size 50m;

  location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```

## Health check

- `GET /health` returns JSON suitable for container/orchestrator health checks.

