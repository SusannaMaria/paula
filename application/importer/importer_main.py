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

from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3TimeStamp
import os
from datetime import datetime
import uuid
from database.database_helper import (
    close_connection,
    close_cursor,
    commit,
    create_cursor,
    insert_artist,
    insert_album,
    insert_track,
    insert_tag,
    execute_query_print_out,
    execute_query,
)
import csv
import signal
import logging

from config_loader import load_config

# Load configuration
config = load_config()
logger = logging.getLogger(__name__)

FIELD_MAP = {
    "artist": "artists.name",
    "genre": "tracks.genre",
    "album": "albums.name",
    "title": "tracks.title",
}

stop_import = False


# Signal handler for graceful interruption
def signal_handler(sig, frame):
    global stop_import
    logger.info("Stopping import after current file.")
    stop_import = True


PROGRESS_FILE = "import_progress.csv"


def get_folder_from_file_path(file_path):
    """Extract the folder path from a file path."""
    return os.path.dirname(file_path)


def initialize_progress_file(directory):
    """Initialize the progress file with all files in the directory."""
    if not os.path.exists(PROGRESS_FILE):
        files = []
        for root, _, file_names in os.walk(directory):
            for file_name in file_names:
                if file_name.lower().endswith((".mp3", ".flac")):
                    files.append([os.path.join(root, file_name), "pending"])

        # Write files to the progress CSV
        with open(PROGRESS_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["file_path", "status"])  # Header
            writer.writerows(files)


def get_files_by_status(status):
    """Retrieve files with the specified status."""
    pending_files = []
    with open(PROGRESS_FILE, mode="r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["status"] == status:
                pending_files.append(row["file_path"])
    return pending_files


def update_file_status(file_path, status):
    """Update the status of a file in the progress file."""
    updated_rows = []
    with open(PROGRESS_FILE, mode="r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["file_path"] == file_path:
                row["status"] = status
            updated_rows.append(row)

    # Write updated rows back to the CSV
    with open(PROGRESS_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["file_path", "status"])
        writer.writeheader()
        writer.writerows(updated_rows)


def record_progress(file_path, status):
    execute_query(
        """
        INSERT INTO import_progress (file_path, status, retry_count)
        VALUES (%s, %s, 0)
        ON CONFLICT (file_path) DO UPDATE
        SET status = EXCLUDED.status,
            retry_count = import_progress.retry_count + 1,
            last_attempt = CURRENT_TIMESTAMP;
        """,
        (file_path, status),
    )


def get_pending_files(directory):
    """Retrieve a list of pending files from the database."""
    result = execute_query(
        """
        SELECT file_path FROM import_progress WHERE status = 'pending';
        """,
        fetch_all=True,
    )
    tracked_files = {row["file_path"] for row in result}

    # Find files in the directory not yet tracked
    all_files = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith((".mp3", ".flac")):
                all_files.add(os.path.join(root, file))

    # Add untracked files to the progress table
    new_files = all_files - tracked_files
    for file_path in new_files:
        print(file_path)
        record_progress(file_path, "pending")

    # Return all pending files
    return list(tracked_files)


def extract_valid_uuids(value):
    valid_uuids = []
    for part in value.split("/"):
        try:
            valid_uuids.append(str(uuid.UUID(part.strip())))
        except ValueError:
            logger.error(f"Invalid UUID found: {part.strip()}. Skipping.")
    return valid_uuids


# Helper to get tags from MP3 or FLAC
def get_tag(metadata, key, default=None):
    if key in metadata:
        value = metadata[key]
        if isinstance(value, list):  # For FLAC or Vorbis comments
            return value[0]
        if hasattr(value, "text"):  # For ID3 tags (like TPE1, TALB, etc.)
            return value.text[0] if value.text else default
        return str(value)  # Convert to string if it's not already
    return default


def process_audio_file(cursor, file_path):
    logger.info(f"Processing: {file_path}")
    folder = get_folder_from_file_path(file_path)

    try:
        # Determine file type and load metadata
        audio = None

        musicbrainz_tags = {}
        # Detect file type and load metadata
        if file_path.lower().endswith(".mp3"):
            audio = MP3(file_path)
            metadata = ID3(file_path)
            for frame in audio.keys():
                if frame.startswith("TXXX:MusicBrainz"):
                    musicbrainz_tags[frame.replace("TXXX:", "")] = audio[frame].text[0]
        elif file_path.lower().endswith(".flac"):
            audio = FLAC(file_path)
            metadata = audio
            for tag in audio:
                if tag.startswith("musicbrainz_"):
                    musicbrainz_tags[tag] = (
                        audio[tag][0] if isinstance(audio[tag], list) else audio[tag]
                    )
        else:
            logger.error(f"Unsupported file format: {file_path}")
            return

        # Extract metadata
        metadata = audio.tags
        # # Check if tags exist and print the keys
        # if metadata:
        #     print("Keys in audio tags:")
        #     for key in metadata.keys():
        #         print(key)
        # else:
        #     print("No tags found in the audio file.")
        # exit()
        artist_name = (
            metadata.get("TPE1", ["Unknown Artist"])[0]
            if "TPE1" in metadata
            else metadata.get("artist", ["Unknown Artist"])[0]
        )
        album_name = (
            metadata.get("TALB", ["Unknown Album"])[0]
            if "TALB" in metadata
            else metadata.get("album", ["Unknown Album"])[0]
        )
        track_title = (
            metadata.get("TIT2", ["Unknown Title"])[0]
            if "TIT2" in metadata
            else metadata.get("title", ["Unknown Title"])[0]
        )
        genre = (
            metadata.get("TCON", [None])[0]
            if "TCON" in metadata
            else metadata.get("genre", [None])[0]
        )
        track_number = (
            metadata.get("TRCK", [None])[0]
            if "TRCK" in metadata
            else metadata.get("tracknumber", [None])[0]
        )

        # Handle year and release_date safely
        raw_year = get_tag(metadata, "TDRC") or get_tag(metadata, "date", None)
        year = None
        if raw_year:
            try:
                # Convert ID3TimeStamp or other year formats to string
                raw_year_str = (
                    str(raw_year) if isinstance(raw_year, ID3TimeStamp) else raw_year
                )
                # Convert to a valid date (default to January 1st)
                year = datetime.strptime(raw_year_str[:4], "%Y").date()
            except ValueError:
                logger.error(f"Invalid year format: {raw_year}. Skipping year.")

        release_date = get_tag(metadata, "TXXX:originalyear")
        if release_date:
            try:
                release_date = datetime.strptime(release_date[:4], "%Y").date()
            except ValueError:
                logger.error(
                    f"Invalid release_date format: {release_date}. Skipping release_date."
                )
                release_date = None
        barcode = get_tag(metadata, "TXXX:BARCODE")

        # Generate UUIDs for missing MusicBrainz IDs
        musicbrainz_release_track_id = get_tag(
            metadata, "TXXX:MusicBrainz Release Track Id"
        ) or musicbrainz_tags.get("musicbrainz_releasetrackid")

        musicbrainz_album_id = get_tag(
            metadata, "TXXX:MusicBrainz Album Id"
        ) or musicbrainz_tags.get("musicbrainz_albumid")
        musicbrainz_artist_id = get_tag(
            metadata, "TXXX:MusicBrainz Album Artist Id"
        ) or musicbrainz_tags.get("musicbrainz_artistid")

        artist_mb_id_valid = True
        album_mb_id_valid = True
        track_mb_id_valid = True

        # if "TXXX:originalyear" in id3:
        #     release_date = id3["TXXX:originalyear"].text[0]
        if not musicbrainz_artist_id:
            musicbrainz_artist_id = str(uuid.uuid4())
            artist_mb_id_valid = False

        if not musicbrainz_album_id:
            musicbrainz_album_id = str(uuid.uuid4())
            album_mb_id_valid = False

        if not musicbrainz_release_track_id:
            musicbrainz_release_track_id = str(uuid.uuid4())
            track_mb_id_valid = False

        artist_ids = extract_valid_uuids(musicbrainz_artist_id)

        artist_ids_db = []

        for musicbrainz_artist_id in artist_ids:
            # Insert artist

            db_artist_id = insert_artist(
                cursor, artist_name, musicbrainz_artist_id, artist_mb_id_valid
            )

            artist_ids_db.append(db_artist_id)

        artist_id = artist_ids_db[0] if artist_ids_db else None
        album_id = insert_album(
            cursor,
            album_name,
            artist_id,
            musicbrainz_album_id,
            barcode,
            year,
            album_mb_id_valid,
            folder,
        )

        track_id = insert_track(
            cursor,
            track_title,
            artist_id,
            album_id,
            genre,
            year,
            track_number,
            file_path,
            musicbrainz_release_track_id,
            track_mb_id_valid,
        )

        if track_id:
            for key in metadata.keys():
                if key.startswith("TXXX"):
                    insert_tag(cursor, track_id, key, get_tag(metadata, key))

        update_file_status(file_path, "imported")
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        update_file_status(file_path, "error")


def get_error_files(max_retries=3):
    result = execute_query(
        """
        SELECT file_path FROM import_progress
        WHERE status = 'error' AND retry_count < %s;
        """,
        (max_retries,),
        fetch_all=True,
    )
    return [row["file_path"] for row in result]


def run_import(directory, retry_errors=False):
    signal.signal(signal.SIGINT, signal_handler)

    logger.info(f"Starting import from directory: {directory}")

    # Initialize or retrieve files
    if not os.path.exists(PROGRESS_FILE):
        initialize_progress_file(directory)

    if retry_errors:
        logger.info("Retrying files with status = 'error'")
        files_to_process = get_files_by_status("error")
    else:
        files_to_process = get_files_by_status("pending")
    cursor = create_cursor()
    for file_path in files_to_process:

        if stop_import:
            logger.info("Import stopped by user.")
            break
        process_audio_file(cursor, file_path)
        commit()

    close_cursor(cursor)
    close_connection()
    logger.info("Import complete.")
