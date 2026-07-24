web: gunicorn app:app -w 4 --timeout 120 --keep-alive 5 --log-level info
worker: python embedding_worker.py
