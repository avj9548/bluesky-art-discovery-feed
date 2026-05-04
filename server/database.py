import os
from peewee import SqliteDatabase, Model, CharField, DateTimeField

# Use WAL mode for better concurrency on Render
db_path = 'feed.db'
db = SqliteDatabase(db_path, pragmas={
    'journal_mode': 'wal',
    'cache_size': -1024 * 64,
    'synchronous': 0,
})


class BaseModel(Model):
    class Meta:
        database = db


class Post(BaseModel):
    uri = CharField(unique=True, primary_key=True)
    cid = CharField()
    reply_parent = CharField(null=True)
    reply_root = CharField(null=True)
    indexed_at = DateTimeField(default=lambda: datetime.utcnow())


class SubscriptionState(BaseModel):
    service = CharField(unique=True, primary_key=True)
    cursor = CharField(null=True)


def init_db():
    db.create_tables([Post, SubscriptionState], safe=True)


# Initialize on import
init_db()