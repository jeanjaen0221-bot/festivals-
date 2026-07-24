# Database migrations

Apply the standard schema migration with `flask db upgrade` after configuring
`DATABASE_URL` and `SECRET_KEY`.

`optional/20260724_02_photo_embeddings_pgvector_optional.py` is deliberately
outside Flask-Migrate's normal version directory. Apply it only once PostgreSQL
has the `vector` extension and Python cosine comparisons have become a
bottleneck. It adds an `ivfflat` cosine index; a controlled backfill must first
convert the existing float32 `embedding` bytea values into `embedding_vector`.
