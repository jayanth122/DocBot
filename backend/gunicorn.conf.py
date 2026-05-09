# Gunicorn config — auto-loaded by gunicorn regardless of startCommand.
# Tuned for Render free tier (512 MB RAM, 1 vCPU).

import multiprocessing

# Single worker to stay within memory limits.
workers = 1

# Use gthread to handle concurrent requests without extra memory.
worker_class = "gthread"
threads = 2

# Must exceed the slowest LLM call (free-tier OpenRouter can take 20-25s).
timeout = 120
graceful_timeout = 15
keepalive = 5

# Render assigns port via $PORT or defaults to 10000.
bind = "0.0.0.0:10000"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
