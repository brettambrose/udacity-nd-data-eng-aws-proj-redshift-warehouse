import configparser
import os

# CONFIG
main_config_path = "dwh.cfg"
main_config = configparser.ConfigParser()
main_config.read(main_config_path)

aws_config_path = os.path.expanduser(os.path.join("~", ".aws", "config"))
aws_config = configparser.ConfigParser()
aws_config.read(aws_config_path)

# DROP TABLES

staging_events_table_drop = "DROP TABLE IF EXISTS staging_events"
staging_songs_table_drop = "DROP TABLE IF EXISTS staging_songs"
songplay_table_drop = "DROP TABLE IF EXISTS songplay"
user_table_drop = "DROP TABLE IF EXISTS users"
song_table_drop = "DROP TABLE IF EXISTS songs"
artist_table_drop = "DROP TABLE IF EXISTS artists"
time_table_drop = "DROP TABLE IF EXISTS time"

# CREATE TABLES

staging_events_table_create= ("""
CREATE TABLE IF NOT EXISTS staging_events (
 artist              text,
 auth		             text,
 firstName           text,
 gender              text,
 itemInSession       text,
 lastName            text,
 length              double precision,
 level               text,
 location            text,
 method              text,
 page                text,
 registration        numeric,
 sessionId           numeric,
 song                text,
 status              numeric,
 ts                  timestamp,
 userAgent           text,
 userId              text
);
""")

staging_songs_table_create = ("""
CREATE TABLE IF NOT EXISTS staging_songs (
 artist_id           text,
 artist_latitude     double precision,
 artist_location     text,
 artist_longitude    double precision,
 artist_name         text,
 duration            double precision,
 num_songs           numeric,
 song_id             text,
 title               text,
 year                numeric
);
""")

songplays_table_create = ("""
CREATE TABLE IF NOT EXISTS songplays (
 songplay_id          INT         IDENTITY(0,1) PRIMARY KEY, 
 start_time           TIMESTAMP   NOT NULL SORTKEY, 
 user_id              VARCHAR     NOT NULL, 
 level                VARCHAR, 
 song_id              VARCHAR     NOT NULL, 
 artist_id            VARCHAR     NOT NULL DISTKEY, 
 session_id           VARCHAR     NOT NULL, 
 location             VARCHAR, 
 user_agent           VARCHAR
);
""")

users_table_create = ("""
CREATE TABLE IF NOT EXISTS users (
 user_id              VARCHAR     PRIMARY KEY, 
 first_name           VARCHAR, 
 last_name            VARCHAR, 
 gender               VARCHAR, 
 level                VARCHAR    SORTKEY
);
""")

songs_table_create = ("""
CREATE TABLE IF NOT EXISTS songs (
 song_id             VARCHAR      PRIMARY KEY, 
 title               VARCHAR, 
 artist_id           VARCHAR      NOT NULL DISTKEY, 
 year                VARCHAR, 
 duration            DOUBLE PRECISION
);
""")

artists_table_create = ("""
CREATE TABLE IF NOT EXISTS artists (
 artist_id           VARCHAR      PRIMARY KEY DISTKEY, 
 name                VARCHAR, 
 location            VARCHAR, 
 latitude            DOUBLE PRECISION, 
 longitude           DOUBLE PRECISION
);
""")

time_table_create = ("""
CREATE TABLE IF NOT EXISTS time (
 start_time         TIMESTAMP     PRIMARY KEY, 
 hour               INT           NOT NULL, 
 day                INT           NOT NULL, 
 week               INT           NOT NULL, 
 month              INT           NOT NULL, 
 year               INT           NOT NULL, 
 weekday            VARCHAR       NOT NULL SORTKEY
)
""")

# STAGING TABLES

staging_events_copy = ("""
 COPY staging_events
 FROM {}
 credentials 'aws_iam_role={}'
 region 'us-west-2'
 JSON {}
 timeformat as 'epochmillisecs'
""").format(
    main_config.get("S3","LOG_DATA"),
    aws_config.get("profile Redshift","role_arn"),
    main_config.get("S3","LOG_JSONPATH")
)

staging_songs_copy = ("""
 COPY staging_songs
 FROM {}
 credentials 'aws_iam_role={}'
 region 'us-west-2'
 JSON 'auto'
""").format(
    main_config.get("S3","SONG_DATA"),
    aws_config.get("profile Redshift","role_arn")
)

# FINAL TABLES

songplays_table_insert = ("""
 INSERT INTO songplays (
  start_time, 
  user_id, 
  level, 
  song_id, 
  artist_id, 
  session_id, 
  location, 
  user_agent
 )
  SELECT
   e.ts,
   e.userid,
   e.level,
   s.song_id,
   s.artist_id,
   e.sessionid,
   e.location,
   e.useragent
  FROM staging_songs s
  INNER JOIN staging_events e
   ON (s.title = e.song AND s.artist_name = e.artist)
  WHERE e.page = 'NextSong'
""")

users_table_insert = ("""
 INSERT INTO users (
  user_id,
  first_name,
  last_name,
  gender,
  level  
 )
  SELECT
   DISTINCT(userid),
   firstname,
   lastname,
   gender,
   level
  FROM staging_events
""")

songs_table_insert = ("""
 INSERT INTO songs (
  song_id, 
  title, 
  artist_id, 
  year, 
  duration
 )
  SELECT
   song_id,
   title,
   artist_id,
   year,
   duration
  FROM staging_songs
""")

artists_table_insert = ("""
 INSERT INTO artists (
  artist_id, 
  name, 
  location, 
  latitude, 
  longitude
 )
  SELECT
   DISTINCT(artist_id),
   artist_name,
   artist_location,
   artist_latitude,
   artist_longitude
  FROM staging_songs
""")

time_table_insert = ("""
 INSERT INTO time (
  start_time,
  hour, 
  day, 
  week, 
  month, 
  year, 
  weekday
 )
  SELECT
   ts,
   EXTRACT(hour from ts),
   EXTRACT(day from ts),
   EXTRACT(week from ts),
   EXTRACT(month from ts),
   EXTRACT(year from ts),
   EXTRACT(dayofweek from ts)
  FROM staging_events
""")

# BASIC DATA QUALITY CHECKS
get_count_songplay = "SELECT COUNT(1) FROM songplays"
get_count_users_table = "SELECT COUNT(1) FROM users"
get_count_artists_table = "SELECT COUNT(1) FROM artists"
get_count_songs_table = "SELECT COUNT(1) FROM songs"
get_count_time_table = "SELECT COUNT(1) FROM time"

# QUERY LISTS
create_table_queries = [staging_events_table_create, staging_songs_table_create, songplays_table_create, users_table_create, songs_table_create, artists_table_create, time_table_create]
drop_table_queries = [staging_events_table_drop, staging_songs_table_drop, songplay_table_drop, user_table_drop, song_table_drop, artist_table_drop, time_table_drop]
copy_table_queries = [staging_events_copy, staging_songs_copy]
insert_table_queries = [songplays_table_insert, users_table_insert, songs_table_insert, artists_table_insert, time_table_insert]
count_table_queries = [get_count_songplay, get_count_users_table, get_count_artists_table, get_count_songs_table, get_count_time_table]