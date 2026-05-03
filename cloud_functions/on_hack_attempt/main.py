"""Cloud Function: on_hack_attempt — Firestore Trigger.

Triggered when a new document is created in the 'hack_attempts' collection.
Writes the event to BigQuery (security_events) for forensic analysis.
If more than 5 attempts from the same masked IP in 10 minutes,
publishes a THREAT_ESCALATION message to Pub/Sub.
"""

import logging
import uuid
from datetime import datetime, timedelta

from google.cloud import bigquery, firestore, pubsub_v1

logger = logging.getLogger('on_hack_attempt')

BQ_DATASET = 'ledgerlogic_analytics'
BQ_TABLE_SECURITY = 'security_events'
PUBSUB_TOPIC = 'threat_escalation'
ESCALATION_THRESHOLD = 5
ESCALATION_WINDOW_MINUTES = 10


def on_hack_attempt(event, context):
    """Firestore trigger: processes new hack attempt documents.

    Args:
        event: Firestore event payload with the hack attempt data.
        context: Event metadata including the resource path.
    """
    hack_data = event.get('value', {}).get('fields', {})

    event_type = _extract_field(hack_data, 'type', 'UNKNOWN')
    masked_ip = _extract_field(hack_data, 'ip_masked', 'XXX.XXX.0')
    path = _extract_field(hack_data, 'path', '/')
    payload_sig = _extract_field(hack_data, 'payload_signature', 'BLOCKED')
    severity = _extract_field(hack_data, 'severity', 'UNCLASSIFIED')
    sentiment_score = float(_extract_field(hack_data, 'sentiment_score', 0.0))
    timestamp = datetime.utcnow().isoformat()

    logger.info('Processing hack attempt: %s from %s on %s | Severity: %s', event_type, masked_ip, path, severity)

    # 1. Write to BigQuery (security_events)
    try:
        bq_client = bigquery.Client()
        table_ref = f'{bq_client.project}.{BQ_DATASET}.{BQ_TABLE_SECURITY}'
        row = {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'masked_ip': masked_ip,
            'path': path,
            'payload_signature': payload_sig,
            'severity': severity,
            'sentiment_score': sentiment_score,
            'timestamp': timestamp
        }
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error('BigQuery insert errors: %s', errors)
        else:
            logger.info('Security event archived to BigQuery: %s', row['event_id'])
    except Exception as e:
        logger.error('BigQuery security stream error: %s', e)

    # 2. Check for escalation (>5 from same IP in 10 min)
    try:
        fs_client = firestore.Client()
        cutoff = datetime.utcnow() - timedelta(minutes=ESCALATION_WINDOW_MINUTES)

        recent_attacks = (
            fs_client.collection('hack_attempts')
            .where('ip_masked', '==', masked_ip)
            .where('timestamp', '>=', cutoff)
            .stream()
        )
        count = sum(1 for _ in recent_attacks)

        if count >= ESCALATION_THRESHOLD:
            logger.warning(
                'THREAT ESCALATION: %d attacks from %s in %d min',
                count, masked_ip, ESCALATION_WINDOW_MINUTES
            )
            _publish_escalation(masked_ip, count, event_type)
    except Exception as e:
        logger.error('Escalation check error: %s', e)


def _publish_escalation(masked_ip: str, count: int, event_type: str) -> None:
    """Publish a THREAT_ESCALATION message to Pub/Sub topic."""
    try:
        publisher = pubsub_v1.PublisherClient()
        project = publisher.common_project_path(publisher.project)
        topic_path = publisher.topic_path(project, PUBSUB_TOPIC)

        message = (
            f'THREAT_ESCALATION: {count} attacks from {masked_ip} | '
            f'type={event_type} | time={datetime.utcnow().isoformat()}'
        )
        publisher.publish(topic_path, message.encode('utf-8'))
        logger.info('Escalation published to Pub/Sub: %s', message)
    except Exception as e:
        logger.error('Pub/Sub publish error: %s', e)


def _extract_field(fields: dict, key: str, default):
    """Extract a value from Firestore event field structure."""
    field = fields.get(key, {})
    for value_type in ('stringValue', 'integerValue', 'doubleValue'):
        if value_type in field:
            return field[value_type]
    return default
