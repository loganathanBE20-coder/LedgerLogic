"""Cloud Function: hourly_aggregation — HTTP Trigger via Cloud Scheduler.

Runs every hour via Cloud Scheduler. Aggregates vote data from BigQuery
and writes a summary to Firestore 'election_summary' document. This powers
the live dashboard without Flask doing the aggregation on every /api/data request.
"""

import logging
from datetime import datetime

import functions_framework
from google.cloud import bigquery, firestore

logger = logging.getLogger('hourly_aggregation')

BQ_DATASET = 'ledgerlogic_analytics'


@functions_framework.http
def hourly_aggregation(request):
    """HTTP-triggered function for hourly BigQuery aggregation.

    Args:
        request: HTTP request object from Cloud Scheduler.

    Returns:
        Tuple of (response_body, status_code).
    """
    logger.info('Starting hourly aggregation at %s', datetime.utcnow().isoformat())

    try:
        bq_client = bigquery.Client()
        fs_client = firestore.Client()

        # 1. Total votes + party-wise breakdown
        party_query = f"""
            SELECT
                candidate AS party,
                COUNT(*) AS total_votes,
                COUNT(DISTINCT constituency_id) AS constituencies_won
            FROM `{bq_client.project}.{BQ_DATASET}.votes_raw`
            GROUP BY candidate
            ORDER BY total_votes DESC
        """
        party_results = list(bq_client.query(party_query).result())

        total_votes = sum(row.total_votes for row in party_results)
        party_summary = [
            {
                'party': row.party,
                'votes': row.total_votes,
                'seats': row.constituencies_won,
                'vote_share': round(row.total_votes / max(total_votes, 1) * 100, 1)
            }
            for row in party_results
        ]

        # 2. Hourly vote rate (last 24 hours)
        hourly_query = f"""
            SELECT
                TIMESTAMP_TRUNC(timestamp, HOUR) AS hour,
                COUNT(*) AS votes
            FROM `{bq_client.project}.{BQ_DATASET}.votes_raw`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
            GROUP BY hour
            ORDER BY hour
        """
        hourly_results = list(bq_client.query(hourly_query).result())
        hourly_trend = [
            {'hour': row.hour.isoformat(), 'votes': row.votes}
            for row in hourly_results
        ]

        # 3. Turnout percentage (assuming 234 constituencies × avg 200k voters)
        total_electorate = 234 * 200000
        turnout_pct = round(total_votes / total_electorate * 100, 2)

        # 4. Write summary to Firestore
        summary = {
            'total_votes': total_votes,
            'turnout_pct': turnout_pct,
            'party_summary': party_summary,
            'hourly_trend': hourly_trend,
            'last_aggregated': datetime.utcnow(),
            'status': 'AGGREGATED'
        }
        fs_client.collection('election_summary').document('latest').set(summary)
        logger.info('Aggregation complete: %d total votes, %.2f%% turnout', total_votes, turnout_pct)

        return {'status': 'ok', 'total_votes': total_votes, 'turnout_pct': turnout_pct}, 200

    except Exception as e:
        logger.error('Hourly aggregation error: %s', e)
        return {'status': 'error', 'message': str(e)}, 500
