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

import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from utils.config_loader import load_config

logger = logging.getLogger(__name__)
conn = None
# Load the configuration
config = load_config()
db_config = config["database"]
isconnected = False


def close_connection():
    conn.close()


def cursor_factory():
    conn = sqlite3.connect(db_config["path"])
    conn.row_factory = sqlite3.Row
    return conn.cursor()


# Establish Database Connection
def get_connection(asrow=False):
    global conn
    try:
        conn = sqlite3.connect(db_config["path"])
        if asrow:
            conn.row_factory = sqlite3.Row
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise


def commit():
    global conn
    conn.commit()


def clean_tables():
    global conn
    cursor = conn.cursor()

    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    cursor.execute("PRAGMA foreign_keys = OFF;")
    # Delete data from each table
    for table in tables:
        cursor.execute(f"DELETE FROM {table[0]};")
        conn.commit()

    cursor.execute("PRAGMA foreign_keys = ON;")

    conn.close()


def backup_database(output_dir="backups"):
    """Backup the database using pg_dump."""
    os.makedirs(output_dir, exist_ok=True)  # Ensure the backup directory exists

    backup_file = os.path.join(
        output_dir,
        f'{db_config.get("dbname")}_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sqlite',
    )

    """Creates a backup of the SQLite database."""
    try:
        # Connect to the backup database
        backup_conn = sqlite3.connect(backup_file)

        with backup_conn:
            # Perform the backup
            conn.backup(backup_conn, pages=1, progress=print_progress)
        logger.info(f"Backup successful: {backup_file}")
    except sqlite3.Error as e:
        logger.ino(f"Error during backup: {e}")
    finally:
        # Close the connections
        if conn:
            conn.close()
        if backup_conn:
            backup_conn.close()


def print_progress(status, remaining, total):
    """Optional: Print backup progress."""
    logger.info(f"Copied {total - remaining} of {total} pages...")


def restore_database(backup_file):
    """Restore the database using pg_restore."""
    global conn
    try:
        # Connect to the backup database
        backup_conn = sqlite3.connect(backup_file)

        with conn:
            # Perform the backup
            backup_conn.backup(conn, pages=1, progress=print_progress)
        logger.info(f"Restore successful: {backup_file}")
    except sqlite3.Error as e:
        logger.ino(f"Error during backup: {e}")
    finally:
        # Close the connections
        if conn:
            conn.close()
        if backup_conn:
            backup_conn.close()


# Initialize Database Schema
def initialize_schema():
    global conn
    schema_sql = """
        CREATE TABLE album_tags (
            album_id integer NOT NULL,
            tag text NOT NULL,
            PRIMARY KEY (album_id, tag),
            FOREIGN KEY (album_id) REFERENCES albums(album_id) ON DELETE CASCADE
        );

        --
        -- Name: albums; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name character varying(500) NOT NULL,
            artist_id integer,
            barcode character varying(20),
            musicbrainz_id uuid,
            release_date date,
            created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            musicbrainz_album_id uuid UNIQUE NOT NULL,
            is_musicbrainz_valid boolean DEFAULT true,
            primary_type text,
            secondary_types text[],
            tags text[],
            folder_path text,
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
        );

        CREATE TABLE artist_relationships (
            artist_id integer NOT NULL,
            related_artist_id integer NOT NULL,
            relationship_type text NOT NULL,
            PRIMARY KEY (artist_id, related_artist_id, relationship_type),
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE,
            FOREIGN KEY (related_artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
        );


        --
        -- Name: artist_tags; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE artist_tags (
            artist_id integer NOT NULL,
            tag text NOT NULL,
            PRIMARY KEY (artist_id, tag),
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
        );


        --
        -- Name: artists; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name character varying(500) NOT NULL,
            musicbrainz_id uuid,
            created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            musicbrainz_artist_id uuid UNIQUE NOT NULL,
            is_musicbrainz_valid boolean DEFAULT true,
            sort_name text,
            type text,
            begin_area text,
            life_span_start date,
            life_span_ended boolean,
            aliases text[],
            life_span_end date,
            wikidata_id character varying(255)
        );

        --
        -- Name: tags; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id integer,
            key character varying(100) NOT NULL,
            value text NOT NULL,
            FOREIGN KEY (track_id) REFERENCES tracks(track_id)
        );

        --
        -- Name: track_features; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE track_features (
            feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id integer NOT NULL,
            danceability real,
            female real,
            male real,
            genre_alternative real,
            genre_blues real,
            genre_electronic real,
            genre_folkcountry real,
            genre_funksoulrnb real,
            genre_jazz real,
            genre_pop real,
            genre_raphiphop real,
            genre_rock real,
            genre_electronic_ambient real,
            genre_electronic_dnb real,
            genre_electronic_house real,
            genre_electronic_techno real,
            genre_electronic_trance real,
            genre_rosamerica_cla real,
            genre_rosamerica_dan real,
            genre_rosamerica_hip real,
            genre_rosamerica_jaz real,
            genre_rosamerica_pop real,
            genre_rosamerica_rhy real,
            genre_rosamerica_roc real,
            genre_rosamerica_spe real,
            genre_tzanetakis_blu real,
            genre_tzanetakis real,
            genre_tzanetakis_cou real,
            genre_tzanetakis_dis real,
            genre_tzanetakis_hip real,
            genre_tzanetakis_jaz real,
            genre_tzanetakis_met real,
            genre_tzanetakis_pop real,
            genre_tzanetakis_reg real,
            genre_tzanetakis_roc real,
            ismir04_rhythm_chachacha real,
            ismir04_rhythm_jive real,
            ismir04_rhythm_quickstep real,
            ismir04_rhythm_rumba_american real,
            ismir04_rhythm_rumba_international real,
            ismir04_rhythm_rumba_misc real,
            ismir04_rhythm_samba real,
            ismir04_rhythm_tango real,
            ismir04_rhythm_viennesewaltz real,
            ismir04_rhythm_waltz real,
            mood_acoustic real,
            mood_electronic real,
            mood_happy real,
            mood_party real,
            mood_relaxed real,
            mood_sad real,
            moods_mirex real,
            timbre real,
            tonal_atonal real,
            voice_instrumental real,
            average_loudness real,
            dynamic_complexity real,
            bpm real,
            chords_key character varying(10),
            chords_number_rate real,
            chords_scale character varying(10),
            danceability_low real,
            FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
        );



        --
        -- Name: track_tags; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE track_tags (
            track_id integer NOT NULL,
            tag text NOT NULL,
            PRIMARY KEY (track_id, tag),
            FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
        );


        --
        -- Name: tracks; Type: TABLE; Schema: public; Owner: postgres
        --

        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title character varying(500) NOT NULL,
            artist_id integer,
            album_id integer,
            genre character varying(100),
            year date,
            track_number character varying(10),
            path text NOT NULL,
            created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            musicbrainz_release_track_id uuid UNIQUE,
            is_musicbrainz_valid boolean DEFAULT true,
            length text DEFAULT 'Unknown',
            recording_id uuid UNIQUE,
            tags text[],
            FOREIGN KEY (album_id) REFERENCES albums(album_id),
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
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


def create_cursor(asrow=False):
    global conn
    get_connection(asrow)
    cursor = conn.cursor()
    return cursor


def close_cursor(cursor):
    cursor.close()


# Example: Insert custom tag
def insert_tag(cursor, track_id, key, value):
    global conn
    try:
        cursor.execute(
            f"INSERT INTO tags (track_id, key, value) VALUES (?, ?, ?);",
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
        # Step 1: Insert if not exists
        cursor.execute(
            """
            INSERT OR IGNORE INTO artists (name, musicbrainz_artist_id, is_musicbrainz_valid)
            VALUES (?, ?, ?);
            """,
            (name, musicbrainz_artist_id, db_valid),
        )

        # Step 2: Retrieve the artist_id
        cursor.execute(
            """
            SELECT artist_id
            FROM artists
            WHERE musicbrainz_artist_id = ?;
            """,
            (musicbrainz_artist_id,),
        )

        artist_id = cursor.fetchone()[0]
        return artist_id
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
    global conn

    if is_musicbrainz_valid:
        db_valid = "TRUE"
    else:
        db_valid = "FALSE"

    try:
        # Step 1: Insert or ignore
        cursor.execute(
            """
            INSERT OR IGNORE INTO albums (
                name, artist_id, musicbrainz_album_id, barcode, release_date, is_musicbrainz_valid, folder_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                name,
                artist_id,
                musicbrainz_album_id,
                barcode,
                release_date,
                db_valid,
                folder,
            ),
        )

        # Step 2: Retrieve the album_id
        cursor.execute(
            """
            SELECT album_id
            FROM albums
            WHERE musicbrainz_album_id = ?;
            """,
            (musicbrainz_album_id,),
        )

        result = cursor.fetchone()
        return result[0] if result else None  # Return album_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert album: {e}")
        sys.exit(1)


def get_tracks_between_by_genre(cursor, genre, lower_bound, upper_bound):
    query = f"SELECT track_id FROM track_features WHERE genre_{genre} BETWEEN ? AND ?;"

    cursor.execute(query, (lower_bound, upper_bound))

    tracks_in_range = cursor.fetchall()

    return [row[0] for row in tracks_in_range]


def get_track_by_id(cursor, track_id):
    SQL_QUERY = """SELECT 
            t.track_id AS track_id,
            t.title AS track_title, 
            a.name AS artist_name, 
            al.name AS album_name,
            t.path as title_path

        FROM 
            tracks t
        JOIN 
            artists a ON t.artist_id = a.artist_id
        JOIN 
            albums al ON t.album_id = al.album_id
        WHERE 
            t.track_id = ?;"""

    cursor.execute(
        SQL_QUERY,
        (track_id,),
    )

    result = cursor.fetchone()
    return result


def get_cover_by_album_id(cursor, album_id):
    SQL_QUERY = """SELECT 
            folder_path 
        FROM 
            albums 
        where
        album_id = ?;"""
    cursor.execute(
        SQL_QUERY,
        (album_id,),
    )
    result = cursor.fetchone()

    folder = result[0]

    config = load_config()
    translate_config = config["local_translate_audio_path"]

    if "albums.folder_path" in translate_config["fields"]:
        folder = (
            folder.replace(translate_config["source"], translate_config["target"], 1)
            if folder.startswith(translate_config["source"])
            else folder
        )

    cover_path = Path(folder) / "cover.jpg"

    if cover_path.exists():
        return cover_path
    else:
        cover_path = Path(folder) / "cover.png"
    if cover_path.exists():
        return cover_path

    return None


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
    length="0:00",
):
    global conn
    if is_musicbrainz_valid:
        db_valid = "TRUE"
    else:
        db_valid = "FALSE"

    try:
        # Step 1: Insert or ignore
        cursor.execute(
            """
            INSERT OR IGNORE INTO tracks (
                title, artist_id, album_id, genre, year, track_number, path, musicbrainz_release_track_id, is_musicbrainz_valid,length
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                length,
            ),
        )

        # Step 2: Retrieve track_id
        cursor.execute(
            """
            SELECT track_id
            FROM tracks
            WHERE musicbrainz_release_track_id = ?;
            """,
            (musicbrainz_release_track_id,),
        )

        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert track: {e}")


def execute_query_print_out(sql_query, params):
    global conn
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query, params)
        results = cursor.fetchall()
        for row in results:
            print(
                f"Title: {row[0]}, Artist: {row[1]}, Album: {row[2]}, Genre: {row[3]}"
            )
    except Exception as e:
        logger.error(f"Error executing query: {sql_query} {e}")
    finally:
        cursor.close()
        conn.close()


def execute_query(cursor, query, params="", fetch_one=False, fetch_all=False):
    global conn
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
        print(f"Error executing query: {query} {e}")
        return None


def update_album_tags(cursor, album_id, tags):
    """Update tags for an album."""
    # Remove existing tags for the album
    execute_query(cursor, "DELETE FROM album_tags WHERE album_id = ?;", (album_id,))

    # Insert new tags
    for tag in tags:
        execute_query(
            cursor,
            "INSERT INTO album_tags (album_id, tag) VALUES (?, ?) ON CONFLICT DO NOTHING;",
            (album_id, tag),
        )


def update_track_tags(cursor, track_id, tags):
    """Update tags for a track."""
    # Remove existing tags for the track
    execute_query(cursor, "DELETE FROM track_tags WHERE track_id = ?;", (track_id,))

    # Insert new tags
    for tag in tags:
        execute_query(
            cursor,
            "INSERT INTO track_tags (track_id, tag) VALUES (?, ?) ON CONFLICT DO NOTHING;",
            (track_id, tag),
        )
