from collections import defaultdict
import time

from atproto import models

from server import config
from server.logger import logger
from server.database import db, Post


# === CORE ARTISTS ===
CORE_ARTISTS_HANDLES = {
    "jamzenn.bsky.social", "foxovh.bsky.social", "ekzonzz.bsky.social",
    "ulvinart.bsky.social", "foxer421.bsky.social", "bonfiredemon.bsky.social",
    "chunie.bsky.social", "x6udpngx.bsky.social", "kalahari.bsky.social",
    "marcknelsen.bsky.social", "mokejumps.bsky.social", "bubblewolf.bsky.social",
}

# Resolve DIDs
resolver = None
CORE_ARTISTS_DIDS = set()
EXTENDED_ARTISTS = set()
MAX_EXTENDED = 300 

def init_core():
    global resolver
    from atproto import IdResolver
    resolver = IdResolver()
    logger.info("Resolving core artists...")
    for handle in CORE_ARTISTS_HANDLES:
        try:
            did = resolver.handle.resolve(handle)
            CORE_ARTISTS_DIDS.add(did)
            logger.info(f"✅ {handle} → {did}")
        except:
            logger.warning(f"Failed to resolve {handle}")
    logger.info(f"Loaded {len(CORE_ARTISTS_DIDS)} core artists")

init_core()


def is_art_post(record: 'models.AppBskyFeedPost.Record') -> bool:
    if record.reply:  # No replies
        return False
    if isinstance(record.embed, (models.AppBskyEmbedImages.Main, models.AppBskyEmbedVideo.Main)):
        return True
    return False


def operations_callback(ops: defaultdict) -> None:
    posts_to_create = []
    
    for created_post in ops[models.ids.AppBskyFeedPost]['created']:
        author_did = created_post['author']
        record = created_post['record']
        uri = created_post['uri']

        is_core = author_did in CORE_ARTISTS_DIDS
        is_extended = author_did in EXTENDED_ARTISTS

        if (is_core or is_extended) and is_art_post(record):
            posts_to_create.append({
                'uri': uri,
                'cid': created_post['cid'],
                'reply_parent': None,
                'reply_root': None,
            })
            logger.info(f"{'✅ Core' if is_core else '🌟 Extended'} art saved: {author_did}")

    if posts_to_create:
        with db.atomic():
            for p in posts_to_create:
                Post.create(**p)
        logger.info(f'📥 Added {len(posts_to_create)} art posts')

    # Clean deletions
    for deleted in ops[models.ids.AppBskyFeedPost]['deleted']:
        Post.delete().where(Post.uri == deleted['uri']).execute()