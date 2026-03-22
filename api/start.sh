#!/bin/bash
cd /var/www/familystock-test/api
source venv/bin/activate
export PYTHONPATH=/var/www/familystock-test/api
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
