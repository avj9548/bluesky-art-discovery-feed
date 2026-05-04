from collections import defaultdict
import time

from atproto import models, IdResolver

from server import config
from server.logger import logger
from server.database import db, Post


# === YOUR CORE ARTISTS ===
CORE_ARTISTS_HANDLES = {
    "jamzenn.bsky.social",
    "foxovh.bsky.social",
    "ekzonzz.bsky.social",
    "ulvinart.bsky.social",
    "foxer421.bsky.social",
    "bonfiredemon.bsky.social",
    "chunie.bsky.social",
    "x6udpngx.bsky.social",
    "kalahari.bsky.social",
    "marcknelsen.bsky.social",
    "mokejumps.bsky.social",
    "bubblewolf.bsky.social",
}

# Resolve handles → DIDs at startup
logger.info("🔄 Resolving core artist handles to DIDs...")
resolver = IdResolver()
CORE_ARTISTS_DIDS = set()
for handle in CORE_ARTISTS_HANDLES:
    try:
        did = resolver.handle.resolve(handle)
        CORE_ARTISTS_DIDS.add(did)
        logger.info(f"✅ Resolved {handle} → {did}")
    except Exception as e:
        logger.warning(f"⚠️ Could not resolve {handle}: {e}")
logger.info(f"Loaded {len(CORE_ARTISTS_DIDS)} core artists")


# Extended artists (people your core artists engage with)
EXTENDED_ARTISTS = set()
MAX_EXTENDED = 200   # Limit to prevent it growing too big


def is_art_post(record: 'models.AppBskyFeedPost.Record') -> bool:
    """Strict filter: original posts with images/video only"""
    if record.reply:  # No replies
        return False
    if isinstance(record.embed, models.AppBskyEmbedImages.Main):
        return True
    if isinstance(record.embed, models.AppBskyEmbedVideo.Main):
        return True
    return False


def operations_callback(ops: defaultdict) -> None:
    posts_to_create = []
    
    # === Handle new posts ===
    for created_post in ops[models.ids.AppBskyFeedPost]['created']:
        author_did = created_post['author']
        record = created_post['record']
        uri = created_post['uri']

        # Core artist original art
        if author_did in CORE_ARTISTS_DIDS:
            if is_art_post(record):
                posts_to_create.append({
                    'uri': uri,
                    'cid': created_post['cid'],
                    'reply_parent': None,
                    'reply_root': None,
                })
                logger.info(f"✅ Core art: {author_did}")

        # Extended artist original art
        elif author_did in EXTENDED_ARTISTS:
            if is_art_post(record):
                posts_to_create.append({
                    'uri': uri,
                    'cid': created_post['cid'],
                    'reply_parent': None,
                    'reply_root': None,
                })
                logger.info(f"🌟 Extended art: {author_did}")

    # === Discover extended artists via likes & reposts ===
    for like in ops[models.ids.AppBskyFeedLike]['created']:
        liker_did = like['author']
        if liker_did in CORE_ARTISTS_DIDS:
            # Get the author of the liked post
            subject = like['record'].subject
            if isinstance(subject, models.ComAtprotoRepoStrongRef.Main):
                liked_author = subject.uri.split('/')[2]  # extract DID
                if liked_author not in CORE_ARTISTS_DIDS and len(EXTENDED_ARTISTS) < MAX_EXTENDED:
                    EXTENDED_ARTISTS.add(liked_author)
                    logger.info(f"➕ Added extended artist via like: {liked_author}")

    for repost in ops[models.ids.AppBskyFeedRepost]['created']:
        reposter_did = repost['author']
        if reposter_did in CORE_ARTISTS_DIDS:
            subject = repost['record'].subject
            if isinstance(subject, models.ComAtprotoRepoStrongRef.Main):
                reposted_author = subject.uri.split('/')[2]
                if reposted_author not in CORE_ARTISTS_DIDS and len(EXTENDED_ARTISTS) < MAX_EXTENDED:
                    EXTENDED_ARTISTS.add(reposted_author)
                    logger.info(f"➕ Added extended artist via repost: {reposted_author}")

    # Save posts
    if posts_to_create:
        with db.atomic():
            for p in posts_to_create:
                Post.create(**p)
        logger.info(f'📥 Added {len(posts_to_create)} art posts to feed')

    # Clean deleted posts
    for deleted in ops[models.ids.AppBskyFeedPost]['deleted']:
        Post.delete().where(Post.uri == deleted['uri']).execute()


# Reduce cursor spam
last_log_time = 0
def on_cursor_updated(cursor: int) -> None:
    global last_log_time
    now = time.time()
    if now - last_log_time > 60:
        logger.debug(f"Cursor: {cursor}")
        last_log_time = now