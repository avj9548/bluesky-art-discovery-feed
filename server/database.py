import os
from peewee import SqliteDatabase

# Use WAL mode for better concurrency
db_path = 'feed.db'
db = SqliteDatabase(db_path, pragmas={
    'journal_mode': 'wal',      # This is the key fix
    'cache_size': -1024 * 64,   # 64MB cache
    'synchronous': 0,
})

def init_db():
    from server.models import Post  # noqa
    db.create_tables([Post], safe=True)