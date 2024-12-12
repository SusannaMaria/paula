"""
    Title: Music Collection Manager
    Description: A Python application to manage and enhance a personal music collection.
    Author: Susanna
    License: MIT License
    Created: 2024

    Copyright (c) 2024 Susanna Maria Hepp

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
"""

import sys
from config_loader import load_config
import psycopg2
from psycopg2.extras import DictCursor
import logging
import os
import subprocess
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Load the configuration
config = load_config()
db_config = config["database"]
isconnected = False


def close_connection():
    conn.close()


# Establish Database Connection
def get_connection():
    try:
        conn = psycopg2.connect(**db_config)

        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise


conn = get_connection()


def commit():
    conn.commit()


def clean_tables():
    query = """
    TRUNCATE TABLE albums,albums,artist_relationships,artist_tags,artists,import_progress,tags,track_features,track_tags,tracks RESTART IDENTITY CASCADE;
    """
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        conn.commit()
        logger.info("Database cleaned successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error cleaning database: {e}")
    finally:
        cursor.close()

    # Remove progress files
    for file_name in ["update_progress.csv", "import_progress.csv"]:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"Removed {file_name}.")
        else:
            print(f"{file_name} does not exist.")


def backup_database(output_dir="backups"):
    """Backup the database using pg_dump."""
    os.makedirs(output_dir, exist_ok=True)  # Ensure the backup directory exists

    backup_file = os.path.join(
        output_dir,
        f'{db_config.get("dbname")}_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sql',
    )

    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = db_config.get("password")
        # Run the pg_dump command
        subprocess.run(
            [
                "pg_dump",
                "-h",
                db_config.get("host"),
                "-U",
                db_config.get("user"),
                "-F",
                "c",
                "-d",
                db_config.get("dbname"),
                "-f",
                backup_file,
            ],
            check=True,
            text=True,
        )
        print(f"Backup successful. File saved to: {backup_file}")
        return backup_file
    except subprocess.CalledProcessError as e:
        print(f"Error during backup: {e}")
        return None


def restore_database(backup_file):
    """Restore the database using pg_restore."""
    try:

        conn = get_connection()
        conn.close()
        # Drop and recreate the database before restoring
        subprocess.run(
            [
                "dropdb",
                "-h",
                db_config.get("host"),
                "-U",
                db_config.get("user"),
                db_config.get("dbname"),
            ],
            check=True,
            text=True,
        )
        subprocess.run(
            [
                "createdb",
                "-h",
                db_config.get("host"),
                "-U",
                db_config.get("user"),
                db_config.get("dbname"),
            ],
            check=True,
            text=True,
        )

        # Run the pg_restore command
        subprocess.run(
            [
                "pg_restore",
                "-h",
                db_config.get("host"),
                "-U",
                db_config.get("user"),
                "-d",
                db_config.get("dbname"),
                backup_file,
            ],
            check=True,
            text=True,
        )
        print(f"Restore successful from file: {backup_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error during restore: {e}")


# Initialize Database Schema
def initialize_schema():
    schema_sql = """
    CREATE TABLE artists (
        artist_id SERIAL PRIMARY KEY,                -- Unique identifier for the artist
        name TEXT NOT NULL,                          -- Artist's name
        sort_name TEXT,                              -- Name used for sorting
        type TEXT,                                   -- Type of artist (e.g., Group, Person)
        begin_area TEXT,                             -- Origin location
        life_span_start DATE,                        -- Start date of the artist's lifespan
        life_span_end DATE,                          -- End date of the artist's lifespan
        life_span_ended BOOLEAN DEFAULT FALSE,       -- End of the artist's lifespan
        aliases TEXT[],                              -- Array of aliases or alternate names
        is_musicbrainz_valid BOOLEAN DEFAULT TRUE,  -- Indicates if the MusicBrainz data is valid
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Timestamp for creation
    );

    CREATE TABLE IF NOT EXISTS albums (
        album_id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        artist_id INT REFERENCES artists(artist_id),
        musicbrainz_album_id UUID UNIQUE,
        barcode TEXT,
        release_date DATE,
        is_musicbrainz_valid BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE tracks (
        track_id SERIAL PRIMARY KEY,                   -- Unique identifier for each track
        title TEXT NOT NULL,                           -- Track title
        artist_id INT REFERENCES artists(artist_id) ON DELETE CASCADE,  -- Associated artist
        album_id INT REFERENCES albums(album_id) ON DELETE CASCADE,    -- Associated album
        genre TEXT,                                    -- Genre of the track
        year DATE,                                     -- Release year of the track
        track_number TEXT,                             -- Track number in the album
        path TEXT NOT NULL,                            -- File path of the track
        length TEXT,                                   -- Duration of the track in a readable format (e.g., 3:45)
        recording_id UUID UNIQUE,                      -- MusicBrainz recording ID
        musicbrainz_release_track_id UUID UNIQUE,     -- MusicBrainz release track ID
        is_musicbrainz_valid BOOLEAN DEFAULT TRUE,    -- Validity flag for MusicBrainz data
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Timestamp for track creation
    );
    
    CREATE TABLE IF NOT EXISTS tags (
        tag_id SERIAL PRIMARY KEY,
        track_id INT REFERENCES tracks(track_id),
        key TEXT NOT NULL,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS import_progress (
        file_path TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'imported', or 'error'
        last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE album_tags (
        album_id INT REFERENCES albums(album_id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (album_id, tag)
    );

    CREATE TABLE track_tags (
        track_id INT REFERENCES tracks(track_id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (track_id, tag)
    );

    CREATE TABLE artist_tags (
        artist_id INT REFERENCES artists(artist_id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        PRIMARY KEY (artist_id, tag)
    );

    CREATE TABLE artist_relationships (
        artist_id INT REFERENCES artists(artist_id) ON DELETE CASCADE,
        related_artist_id INT REFERENCES artists(artist_id) ON DELETE CASCADE,
        relationship_type TEXT NOT NULL,
        PRIMARY KEY (artist_id, related_artist_id, relationship_type)
    );
    CREATE TABLE track_features (
        feature_id SERIAL PRIMARY KEY,
        track_id INT NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
        danceability REAL,
        female REAL,
        male REAL,
        genre_alternative REAL,
        genre_blues REAL,
        genre_electronic REAL,
        genre_folkcountry REAL,
        genre_funksoulrnb REAL,
        genre_jazz REAL,
        genre_pop REAL,
        genre_raphiphop REAL,
        genre_rock REAL,
        genre_electronic_ambient REAL,
        genre_electronic_dnb REAL,
        genre_electronic_house REAL,
        genre_electronic_techno REAL,
        genre_electronic_trance REAL,
        genre_rosamerica_cla REAL,
        genre_rosamerica_dan REAL,
        genre_rosamerica_hip REAL,
        genre_rosamerica_jaz REAL,
        genre_rosamerica_pop REAL,
        genre_rosamerica_rhy REAL,
        genre_rosamerica_roc REAL,
        genre_rosamerica_spe REAL,
        genre_tzanetakis_blu REAL,
        genre_tzanetakis REAL,
        genre_tzanetakis_cou REAL,
        genre_tzanetakis_dis REAL,
        genre_tzanetakis_hip REAL,
        genre_tzanetakis_jaz REAL,
        genre_tzanetakis_met REAL,
        genre_tzanetakis_pop REAL,
        genre_tzanetakis_reg REAL,
        genre_tzanetakis_roc REAL,
        ismir04_rhythm_ChaChaCha REAL,
        ismir04_rhythm_Jive REAL,
        ismir04_rhythm_Quickstep REAL,
        ismir04_rhythm_Rumba_American REAL,
        ismir04_rhythm_Rumba_International REAL,
        ismir04_rhythm_Rumba_Misc REAL,
        ismir04_rhythm_Samba REAL,
        ismir04_rhythm_Tango REAL,
        ismir04_rhythm_VienneseWaltz REAL,
        ismir04_rhythm_Waltz REAL,
        mood_acoustic REAL,
        mood_electronic REAL,
        mood_happy REAL,
        mood_party REAL,
        mood_relaxed REAL,
        mood_sad REAL,
        moods_mirex REAL,
        timbre REAL,
        tonal_atonal REAL,
        voice_instrumental REAL
    );
    """
    cursor = conn.cursor()
    try:
        cursor.execute(schema_sql)
        conn.commit()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing schema: {e}")
    finally:
        cursor.close()


def create_cursor():
    cursor = conn.cursor()
    return cursor


def close_cursor(cursor):
    cursor.close()


# Example: Insert custom tag
def insert_tag(cursor, track_id, key, value):

    try:
        cursor.execute(
            cursor,
            "INSERT INTO tags (track_id, key, value) VALUES (%s, %s, %s);",
            (track_id, key, value),
        )
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert tag: {e}")


def insert_artist(cursor, name, musicbrainz_artist_id, is_musicbrainz_valid):

    if is_musicbrainz_valid:
        db_valid = "TRUE"
    else:
        db_valid = "FALSE"

    try:
        cursor.execute(
            """
            WITH ins AS (
                INSERT INTO artists (name, musicbrainz_artist_id,is_musicbrainz_valid )
                VALUES (%s, %s, %s)
                ON CONFLICT (musicbrainz_artist_id) DO NOTHING
                RETURNING artist_id
            )
            SELECT artist_id FROM ins
            UNION ALL
            SELECT artist_id FROM artists WHERE musicbrainz_artist_id = %s;
            """,
            (name, musicbrainz_artist_id, db_valid, musicbrainz_artist_id),
        )
        result = cursor.fetchone()
        return result[0] if result else None  # Return artist_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert artist: {e}")


# Example: Insert album
def insert_album(
    cursor,
    name,
    artist_id,
    musicbrainz_album_id,
    barcode=None,
    release_date=None,
    is_musicbrainz_valid=True,
    folder=None,
):

    if is_musicbrainz_valid:
        db_valid = "TRUE"
    else:
        db_valid = "FALSE"

    try:
        cursor.execute(
            """
            WITH ins AS (
                INSERT INTO albums (name, artist_id, musicbrainz_album_id, barcode, release_date,is_musicbrainz_valid,folder_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (musicbrainz_album_id) DO NOTHING
                RETURNING album_id
            )
            SELECT album_id FROM ins
            UNION ALL
            SELECT album_id FROM albums WHERE musicbrainz_album_id = %s;
            """,
            (
                name,
                artist_id,
                musicbrainz_album_id,
                barcode,
                release_date,
                db_valid,
                folder,
                musicbrainz_album_id,
            ),
        )
        result = cursor.fetchone()
        return result[0] if result else None  # Return album_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert album: {e}")
        sys.exit(1)


# Example: Insert track
def insert_track(
    cursor,
    title,
    artist_id,
    album_id,
    genre,
    year,
    track_number,
    path,
    musicbrainz_release_track_id,
    is_musicbrainz_valid,
):

    if is_musicbrainz_valid:
        db_valid = "TRUE"
    else:
        db_valid = "FALSE"

    try:
        cursor.execute(
            """
            INSERT INTO tracks (title, artist_id, album_id, genre, year, track_number, path, musicbrainz_release_track_id, is_musicbrainz_valid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (musicbrainz_release_track_id) DO NOTHING
            RETURNING track_id;
            """,
            (
                title,
                artist_id,
                album_id,
                genre,
                year,
                track_number,
                path,
                musicbrainz_release_track_id,
                db_valid,
            ),
        )
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert track: {e}")


def execute_query_print_out(sql_query, params):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query, params)
        results = cursor.fetchall()
        for row in results:
            print(
                f"Title: {row[0]}, Artist: {row[1]}, Album: {row[2]}, Genre: {row[3]}"
            )
    except Exception as e:
        logger.error(f"Error executing query: {e}")
    finally:
        cursor.close()
        conn.close()


def execute_query(cursor, query, params=None, fetch_one=False, fetch_all=False):
    try:
        cursor.execute(query, params)
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = None
        return result
    except Exception as e:
        conn.rollback()
        print(f"Error executing query: {e}")
        return None


def update_album_tags(cursor, album_id, tags):
    """Update tags for an album."""
    # Remove existing tags for the album
    execute_query(cursor, "DELETE FROM album_tags WHERE album_id = %s;", (album_id,))

    # Insert new tags
    for tag in tags:
        execute_query(
            cursor,
            "INSERT INTO album_tags (album_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (album_id, tag),
        )


def update_track_tags(cursor, track_id, tags):
    """Update tags for a track."""
    # Remove existing tags for the track
    execute_query(cursor, "DELETE FROM track_tags WHERE track_id = %s;", (track_id,))

    # Insert new tags
    for tag in tags:
        execute_query(
            cursor,
            "INSERT INTO track_tags (track_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (track_id, tag),
        )
