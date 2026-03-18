#!/bin/bash
cd /var/www/familystock/api
source venv/bin/activate
export PYTHONPATH=/var/www/familystock/api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
