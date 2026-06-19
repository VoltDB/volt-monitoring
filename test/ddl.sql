-- Schema that lights up the tables, partitions, procedures, memory, export and
-- TTL dashboards. Kept intentionally small; the workload drives the rest.

CREATE TABLE events (
  id            BIGINT       NOT NULL,
  ts            TIMESTAMP    NOT NULL,
  category      VARCHAR(32),
  payload       VARCHAR(256),
  PRIMARY KEY (id)
);
PARTITION TABLE events ON COLUMN id;
CREATE INDEX events_category ON events (category);

-- Replicated reference table.
CREATE TABLE config (
  k   VARCHAR(64) NOT NULL,
  v   VARCHAR(256),
  PRIMARY KEY (k)
);

-- TTL table so the TTL dashboard has something to show.
CREATE TABLE sessions (
  session_id  BIGINT      NOT NULL,
  created     TIMESTAMP   NOT NULL,
  data        VARCHAR(128),
  PRIMARY KEY (session_id)
) USING TTL 1 MINUTES ON COLUMN created;
PARTITION TABLE sessions ON COLUMN session_id;
-- TTL requires an index whose first column is the TTL column, otherwise every
-- delete round aborts ("Could not find index to support LowImpactDelete") and
-- no rows are purged and no voltdb_ttl_* metrics are produced.
CREATE INDEX sessions_created ON sessions (created);

-- Export stream feeding the (discarding) "archive" target.
CREATE STREAM events_archive
  PARTITION ON COLUMN id
  EXPORT TO TARGET archive (
  id        BIGINT       NOT NULL,
  ts        TIMESTAMP    NOT NULL,
  category  VARCHAR(32)
);

-- A simple multi-statement procedure so the procedures dashboard sees a
-- user procedure (not just the auto-generated CRUD ones).
CREATE PROCEDURE record_event
  PARTITION ON TABLE events COLUMN id
AS BEGIN
  INSERT INTO events (id, ts, category, payload) VALUES (?, NOW, ?, ?);
  INSERT INTO events_archive (id, ts, category) VALUES (?, NOW, ?);
END;
