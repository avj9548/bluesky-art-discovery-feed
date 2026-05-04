from atproto import Client, models
from server.data_filter import CORE_ARTISTS_DIDS, EXTENDED_ARTISTS, MAX_EXTENDED
from server.logger import logger
from dotenv import load_dotenv
import os
import time

load_dotenv()

client = Client()
client.login(os.getenv("HANDLE"), os.getenv("PASSWORD"))

logger.info("🚀 Running STRONG backfill (likes + reposts + pagination)...")

added = 0

for did in list(CORE_ARTISTS_DIDS):
    logger.info(f"Scanning {did}...")

    # Likes (publicly queryable via API)
    try:
        cursor = None
        for _ in range(3):  # up to 3 pages
            resp = client.app.bsky.feed.get_actor_likes(
                params={'actor': did, 'limit': 50, 'cursor': cursor}
            )
            for item in resp.likes:
                if hasattr(item.subject, 'uri'):
                    liked_did = item.subject.uri.split('/')[2]
                    if liked_did not in CORE_ARTISTS_DIDS and liked_did not in EXTENDED_ARTISTS and len(EXTENDED_ARTISTS) < MAX_EXTENDED:
                        EXTENDED_ARTISTS.add(liked_did)
                        added += 1
                        logger.info(f"➕ Added via like: {liked_did}")
            cursor = resp.cursor
            if not cursor:
                break
            time.sleep(1)
    except Exception as e:
        logger.debug(f"Likes scan failed for {did}: {e}")

    # Reposts (more reliable)
    try:
        resp = client.app.bsky.feed.get_author_feed(
            params={'actor': did, 'limit': 50, 'filter': 'posts_with_reposts'}
        )
        for feed_view in resp.feed:
            if feed_view.reason:  # it's a repost
                reposted_did = feed_view.post.author.did
                if reposted_did not in CORE_ARTISTS_DIDS and reposted_did not in EXTENDED_ARTISTS and len(EXTENDED_ARTISTS) < MAX_EXTENDED:
                    EXTENDED_ARTISTS.add(reposted_did)
                    added += 1
                    logger.info(f"➕ Added via repost: {reposted_did}")
    except Exception as e:
        logger.debug(f"Repost scan failed for {did}: {e}")

    time.sleep(2)

logger.info(f"✅ Strong backfill finished! Total extended artists: {len(EXTENDED_ARTISTS)} (+{added} this run)")
print(f"Added {added} new extended artists.")