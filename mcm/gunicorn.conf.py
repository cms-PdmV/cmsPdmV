import multiprocessing
import os

host = os.environ.get('MCM_HOST', '0.0.0.0')
port = os.environ.get('MCM_PORT', '8000')
bind = f"{host}:{port}"
workers = multiprocessing.cpu_count() * 2 + 1
