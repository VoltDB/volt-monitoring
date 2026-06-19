-- Identical DR schema on both clusters (XDCR requires matching schemas).
CREATE TABLE events (
  id   BIGINT       NOT NULL,
  ts   TIMESTAMP    NOT NULL,
  val  VARCHAR(128),
  PRIMARY KEY (id)
);
PARTITION TABLE events ON COLUMN id;
DR TABLE events;

CREATE TABLE refdata (
  k  VARCHAR(64) NOT NULL,
  v  VARCHAR(128),
  PRIMARY KEY (k)
);
DR TABLE refdata;
