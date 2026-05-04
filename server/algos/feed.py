from datetime import datetime
from typing import Optional

from server.database import Post
from server.logger import logger
from server import config
from server.data_filter import EXTENDED_ARTISTS

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

    posts = list(query.limit(limit + 30))

    now = datetime.utcnow()
    scored = []

    for p in posts:
        age_hours = (now - p.indexed_at).total_seconds() / 3600
        decay = max(0.1, 1.0 / (1 + age_hours / 12))

        author_did = p.uri.split('/')[2]
        is_extended = author_did in EXTENDED_ARTISTS

        # Strong discovery bias
        boost = 3.0 if is_extended else 1.0

        score = decay * boost
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    feed_items = [{'post': p.uri} for _, p in scored[:limit]]

    next_cursor = CURSOR_EOF
    if len(scored) > limit:
        last = scored[limit - 1][1]
        next_cursor = f"{int(last.indexed_at.timestamp() * 1000)}::{last.cid}"

    logger.info(f"📤 Returning {len(feed_items)} posts ({sum(1 for _,p in scored if str(p.uri).split('/')[2] in EXTENDED_ARTISTS)} from extended)")
    return {
        'cursor': next_cursor,
        'feed': feed_items
    }