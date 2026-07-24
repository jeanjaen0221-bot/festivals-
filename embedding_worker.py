"""Worker Railway: `python embedding_worker.py` ou reprise `--retry-failed`."""
import argparse
import logging
import time

from app import app
from embedding_queue import claim_next_job, process_job, retry_failed_jobs


def main():
    parser = argparse.ArgumentParser(description='Worker de génération des embeddings visuels')
    parser.add_argument('--once', action='store_true', help='Traite au plus un job puis quitte')
    parser.add_argument('--retry-failed', action='store_true', help='Réarme les jobs échoués avant traitement')
    parser.add_argument('--poll-seconds', type=float, default=5, help='Délai sans job (défaut: 5)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    with app.app_context():
        if args.retry_failed:
            logging.getLogger(__name__).info('embedding_jobs_requeued count=%s', retry_failed_jobs())
        while True:
            job_id = claim_next_job()
            if job_id is not None:
                process_job(job_id)
            elif args.once:
                break
            else:
                time.sleep(args.poll_seconds)


if __name__ == '__main__':
    main()
