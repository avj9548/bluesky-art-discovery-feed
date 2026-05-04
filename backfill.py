from atproto import Client
from server.data_filter import CORE_ARTISTS_DIDS, EXTENDED_ARTISTS, MAX_EXTENDED
from server.logger import logger
import time
from dotenv import load_dotenv
import os

load_dotenv()

client = Client()
client.login(os.getenv("HANDLE"), os.getenv("PASSWORD"))

logger.info("🚀 Starting improved backfill (likes + reposts)...")

added = 0

for did in list(CORE_ARTISTS_DIDS):
    logger.info(f"🔍 Scanning activity for: {did}")
    
    # === Try Likes ===
    try:
        response = client.app.bsky.feed.get_actor_likes(
            params={'actor': did, 'limit': 30}
        )
        for item in response.likes:
            if hasattr(item.subject, 'uri'):
                liked_did = item.subject.uri.split('/')[2]
                if liked_did not in CORE_ARTISTS_DIDS and liked_did not in EXTENDED_ARTISTS and len(EXTENDED_ARTISTS) < MAX_EXTENDED:
                    EXTENDED_ARTISTS.add(liked_did)
                    added += 1
                    logger.info(f"➕ Added via like: {liked_did}")
    except Exception as e:
        logger.debug(f"Likes skipped for {did} (probably private): {type(e).__name__}")

    # === Try Reposts (usually more accessible) ===
    try:
        response = client.app.bsky.feed.get_author_feed(
            params={'actor': did, 'limit': 30, 'filter': 'posts_with_reposts'}
        )
        for feed_view in response.feed:
            if feed_view.reason and hasattr(feed_view.reason, 'by'):  # it's a repost
                reposted_did = feed_view.post.author.did
                if reposted_did not in CORE_ARTISTS_DIDS and reposted_did not in EXTENDED_ARTISTS and len(EXTENDED_ARTISTS) < MAX_EXTENDED:
                    EXTENDED_ARTISTS.add(reposted_did)
                    added += 1
                    logger.info(f"➕ Added via repost: {reposted_did}")
    except Exception as e:
        logger.debug(f"Reposts scan skipped for {did}: {type(e).__name__}")

    time.sleep(2)  # Be gentle

logger.info(f"✅ Backfill finished! Total extended artists: {len(EXTENDED_ARTISTS)}")
print(f"\n🎉 Added {added} new extended artists.")
print(f"   Your feed now knows about {len(EXTENDED_ARTISTS)} discovered artists.")