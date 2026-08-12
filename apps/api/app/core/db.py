"""Raw Postgres access (Prompt 4).

Section 6 puts Supabase/Postgres behind DATABASE_URL. There's no ORM in
the spec's stack, so this is a thin psycopg wrapper -- one connection
per request, autocommit off, callers commit explicitly after a
successful write so a mid-handler exception rolls back cleanly.

RLS is enabled on every table (Prompt 2), but this connection uses
DATABASE_URL's role directly rather than presenting a user JWT, so it
behaves like Supabase's service_role (RLS-bypassing) client -- correct
here because route-level authorization already happened via
app.core.security before these functions run, and some operations
(signup, before any row exists to scope RLS to) have no authenticated
user to run RLS as in the first place.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.core.config import Settings


@contextmanager
def get_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()
