"""Cloud Function: on_vote_cast — Firestore Trigger.

Triggered when a new document is created in the 'votes' collection.
Streams the vote into BigQuery (votes_raw) for immutable archival,
recalculates constituency stats, and logs a structured audit entry.
"""

import logging
import uuid
from datetime import datetime

from google.cloud import bigquery, firestore

logger = logging.getLogger('on_vote_cast')

BQ_DATASET = 'ledgerlogic_analytics'
BQ_TABLE_VOTES = 'votes_raw'


def on_vote_cast(event, context):
    """Firestore trigger: processes new vote documents.

    Args:
        event: Firestore event payload containing the new document data.
        context: Event metadata including the resource path.
    """
    vote_data = event.get('value', {}).get('fields', {})

    # Extract fields from Firestore document
    name_hashed = _extract_field(vote_data, 'name_hashed', '')
    candidate = _extract_field(vote_data, 'candidate', '')
    constituency_id = int(_extract_field(vote_data, 'constituency_id', 0))
    timestamp = datetime.utcnow().isoformat()

    logger.info('Processing vote: %s -> constituency %d', candidate, constituency_id)

    # 1. Stream to BigQuery (votes_raw)
    try:
        bq_client = bigquery.Client()
        table_ref = f'{bq_client.project}.{BQ_DATASET}.{BQ_TABLE_VOTES}'
        row = {
            'vote_id': str(uuid.uuid4()),
            'name_hashed': name_hashed,
            'candidate': candidate,
            'constituency_id': constituency_id,
            'party': candidate,
            'timestamp': timestamp,
            'session_id': _extract_field(vote_data, 'session_id', '')
        }
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error('BigQuery insert errors: %s', errors)
        else:
            logger.info('Vote streamed to BigQuery: %s', row['vote_id'])
    except Exception as e:
        logger.error('BigQuery stream error: %s', e)

    # 2. Recalculate constituency stats → Firestore
    try:
        fs_client = firestore.Client()
        stats_ref = fs_client.collection('constituency_stats').document(str(constituency_id))

        # Atomic increment using Firestore transactions
        stats_ref.set({
            'constituency_id': constituency_id,
            'last_vote_candidate': candidate,
            'last_updated': datetime.utcnow(),
            'total_votes': firestore.Increment(1)
        }, merge=True)
        logger.info('Constituency %d stats updated', constituency_id)
    except Exception as e:
        logger.error('Firestore stats update error: %s', e)

    # 3. Structured audit log
    logger.info(
        'AUDIT: vote_cast | constituency=%d | candidate=%s | hash=%s',
        constituency_id, candidate, name_hashed
    )


def _extract_field(fields: dict, key: str, default):
    """Extract a value from Firestore event field structure."""
    field = fields.get(key, {})
    for value_type in ('stringValue', 'integerValue', 'doubleValue'):
        if value_type in field:
            return field[value_type]
    return default
