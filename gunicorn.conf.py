import os

# Workers
workers = int(os.environ.get("WEB_CONCURRENCY", 2))

# Timeout: VPS redemption can take 15-30s, default 30s kills the worker
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))

# Bind
bind = "0.0.0.0:" + os.environ.get("PORT", "8000")

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
