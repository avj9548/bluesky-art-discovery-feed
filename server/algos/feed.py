from datetime import datetime, timedelta
from typing import Optional

from server.database import Post
from server.logger import logger
from server import config
from server.data_filter import EXTENDED_ARTISTS   # ← this is the key line

uri = config.FEED_URI
CURSOR_EOF = 'eof'


def handler(cursor: Optional[str], limit: int) -> dict:
    limit = min(int(limit), 100)

    query = Post.select().order_by(Post.indexed_at.desc())

    if cursor and cursor != CURSOR_EOF:
        try:
            ts, cid = cursor.split('::')
            indexed_at = datetime.fromtimestamp(int(ts) / 1000)
            query = query.where(
                (Post.indexed_at < indexed_at) |
                ((Post.indexed_at == indexed_at) & (Post.cid < cid))
            )
        except:
            pass

    posts = list(query.limit(limit + 20))   # extra buffer for sorting

    now = datetime.utcnow()
    scored = []

    for p in posts:
        # Basic time decay (newer = stronger)
        age_hours = (now - p.indexed_at).total_seconds() / 3600
        decay = max(0.05, 1.0 / (1 + age_hours / 8))   # decays slower than before

        # Boost for extended artists (discovery value)
        is_extended = str(p.uri).split('/')[2] in EXTENDED_ARTISTS
        boost = 1.8 if is_extended else 1.0

        score = decay * boost
        scored.append((score, p))

    # Sort by score (highest first)
    scored.sort(key=lambda x: x[0], reverse=True)

    feed_items = [{'post': p.uri} for _, p in scored[:limit]]

    next_cursor = CURSOR_EOF
    if len(scored) > limit:
        last = scored[limit - 1][1]
        next_cursor = f"{int(last.indexed_at.timestamp() * 1000)}::{last.cid}"

    logger.info(f"📤 Returning {len(feed_items)} ranked posts "
                f"({sum(1 for _,p in scored if str(p.uri).split('/')[2] in EXTENDED_ARTISTS)} from extended)")
    
    return {
        'cursor': next_cursor,
        'feed': feed_items
    }