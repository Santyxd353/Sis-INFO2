import os

bind = '0.0.0.0:8000'
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
timeout = 60
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
capture_output = True
# Lifecycle is managed by systemd/Docker. No writable home directory is needed.
control_socket_disable = True
# Caddy is the only published ingress; backend has no host port.
forwarded_allow_ips = '*'
