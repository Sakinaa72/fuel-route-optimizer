import os

port = int(os.getenv("PORT", "8000"))
if not 1 <= port <= 65535:
    raise RuntimeError("PORT must be between 1 and 65535.")
bind = f"0.0.0.0:{port}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = 2
timeout = 90
graceful_timeout = 25
accesslog = "-"
errorlog = "-"
capture_output = True
# Log the URL path only: query strings can contain personal address data.
access_log_format = '{"event":"http_request","method":"%(m)s","path":"%(U)s","status":%(s)s}'
