#!/bin/bash

# Start the RQ worker in the background
rq worker &

# Start the main application
exec gunicorn --workers=$WORKERS --timeout=240 concurrent_gary:app --bind 0.0.0.0:8000
