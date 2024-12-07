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

import requests
import time
import logging
from database.database_helper import (
    close_connection,
    close_cursor,
    commit,
    create_cursor,
    execute_query,
    update_album_tags,
    update_track_tags,
)

import csv
import os
import signal

logger = logging.getLogger(__name__)


PROGRESS_FILE = "update_progress.csv"

stop_update = False


# Signal handler for graceful interruption
def signal_handler(sig, frame):
    global stop_update
    logger.info("Stopping update after current file.")
    stop_update = True


def initialize_progress_file(cursor):
    """Initialize the progress file if it doesn't exist."""
    if not os.path.exists(PROGRESS_FILE):
        entities = []

        # Fetch artists, albums, and tracks with MusicBrainz IDs
        for entity_type, query in [
            ("artist", "SELECT artist_id, musicbrainz_artist_id FROM artists"),
            ("album", "SELECT album_id, musicbrainz_album_id FROM albums"),
            ("track", "SELECT track_id, musicbrainz_release_track_id FROM tracks"),
        ]:
            result = execute_query(cursor, query, fetch_all=True)
            for row in result:
                entities.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": row[0],
                        "musicbrainz_id": row[1],
                        "status": "pending",
                    },
                )

        # Write entities to CSV
        with open(PROGRESS_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=["entity_type", "entity_id", "musicbrainz_id", "status"],
            )
            writer.writeheader()
            writer.writerows(entities)


def get_pending_items():
    """Retrieve pending items from the progress file."""
    pending_items = []
    with open(PROGRESS_FILE, mode="r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["status"] == "pending":
                pending_items.append(row)
    return pending_items


def get_items_to_update(cursor, table_name):
    """Fetch items with MusicBrainz IDs that need updating."""
    return execute_query(
        cursor,
        f"SELECT * FROM {table_name} WHERE is_musicbrainz_valid IS TRUE;",
        fetch_all=True,
    )


def update_item_status(entity_type, entity_id, status):
    """Update the status of an item in the progress file."""
    updated_rows = []
    with open(PROGRESS_FILE, mode="r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["entity_type"] == entity_type and int(row["entity_id"]) == entity_id:
                row["status"] = status
            updated_rows.append(row)

    # Write updated rows back to the CSV
    with open(PROGRESS_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=["entity_type", "entity_id", "musicbrainz_id", "status"]
        )
        writer.writeheader()
        writer.writerows(updated_rows)


def query_musicbrainz(entity_type, mbid, includes=None):
    """Query the MusicBrainz API."""
    base_url = "https://musicbrainz.org/ws/2"
    params = {"fmt": "json"}
    if includes:
        params["inc"] = includes
    url = f"{base_url}/{entity_type}/{mbid}"

    try:
        headers = {"User-Agent": "Paula/1.0 (susanna@olsoni.de)"}
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        time.sleep(0.7)  # Respect API rate limit
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error querying MusicBrainz for {entity_type} {mbid}: {e}")
        return None


def update_artist_metadata(cursor, artist_id, musicbrainz_data):
    """Update artist metadata in the database, including is_musicbrainz_valid."""
    # print(musicbrainz_data)
    if musicbrainz_data:
        # Extract and update fields only if data is valid
        name = musicbrainz_data.get("name")
        sort_name = musicbrainz_data.get("sort-name")
        type_ = musicbrainz_data.get("type")
        begin_area_struct = musicbrainz_data.get("begin-area", {})
        if begin_area_struct:
            begin_area = begin_area_struct.get("name")
        else:
            begin_area = None
        life_span = musicbrainz_data.get("life-span", {})

        if life_span:
            life_span_start = life_span.get("begin")
            life_span_end = life_span.get("end")
            life_span_ended = life_span.get("ended")

            # Check if life_span_start is a valid string, not a bool
            if isinstance(life_span_start, str):
                if len(life_span_start) == 4:  # If only the year is provided
                    life_span_start = f"{life_span_start}-01-01"
                elif len(life_span_start) == 7:  # Year and month
                    life_span_start = f"{life_span_start}-01"
            else:
                life_span_start = None

            # Check if life_span_start is a valid string, not a bool
            if isinstance(life_span_end, str):
                if len(life_span_end) == 4:  # If only the year is provided
                    life_span_end = f"{life_span_end}-01-01"
                elif len(life_span_end) == 7:  # Year and month
                    life_span_end = f"{life_span_end}-01"
            else:
                life_span_end = None
        else:
            life_span_start = None
            life_span_end = None

        aliases = [alias["name"] for alias in musicbrainz_data.get("aliases", [])]
        is_valid = True

        query = """
            UPDATE artists
            SET name = %s,
                sort_name = %s,
                type = %s,
                begin_area = %s,
                life_span_start = %s,
                life_span_end = %s,
                life_span_ended = %s,
                aliases = %s,
                is_musicbrainz_valid = %s
            WHERE artist_id = %s;
        """
        execute_query(
            cursor,
            query,
            (
                name,
                sort_name,
                type_,
                begin_area,
                life_span_start,
                life_span_end,
                life_span_ended,
                aliases,
                is_valid,
                artist_id,
            ),
        )
    else:
        # Mark as invalid if no data is available
        query = """
            UPDATE artists
            SET is_musicbrainz_valid = FALSE
            WHERE artist_id = %s;
        """
        execute_query(cursor, query, (artist_id,))

    # Fetch and update tags
    tags = fetch_artist_tags(musicbrainz_data["id"])
    update_artist_tags(cursor, artist_id, tags)

    # Fetch and update relationships
    relationships = fetch_artist_relationships(musicbrainz_data["id"])
    update_artist_relationships(cursor, artist_id, relationships)


def update_album_metadata(cursor, album_id, musicbrainz_data):
    """Update album metadata and tags in the database."""
    if musicbrainz_data:
        # Extract and update fields

        release_group = musicbrainz_data.get("release-group")
        if release_group:
            title = release_group.get("title")
            primary_type = release_group.get("primary-type")
            secondary_types = release_group.get("secondary-types", [])
            release_date = release_group.get("first-release-date")
            if len(release_date) == 0:
                release_date = None
            if len(release_date) == 4:  # If only the year is provided
                release_date = f"{release_date}-01-01"
            elif len(release_date) == 7:  # Year and month
                release_date = f"{release_date}-01"

            tags = [tag["name"] for tag in release_group.get("tags", [])]

            logger.debug((title, primary_type, secondary_types, release_date, album_id))

            is_valid = True

        query = """
            UPDATE albums
            SET name = %s,
                primary_type = %s,
                secondary_types = %s,
                release_date = %s,
                is_musicbrainz_valid = %s
            WHERE album_id = %s;
        """
        execute_query(
            cursor,
            query,
            (title, primary_type, secondary_types, release_date, is_valid, album_id),
        )

        # Update tags in the album_tags table
        if tags:
            update_album_tags(cursor, album_id, tags)
    else:
        # Mark as invalid if no data is available
        query = """
            UPDATE albums
            SET is_musicbrainz_valid = FALSE
            WHERE album_id = %s;
        """
        execute_query(cursor, query, (album_id,))


def update_track_metadata(cursor, track_id, musicbrainz_id, musicbrainz_data):
    """Update track metadata and tags in the database."""
    if musicbrainz_data:
        # Extract and update fields
        track = None
        for track_item in musicbrainz_data["releases"][0]["media"][0]["tracks"]:
            if track_item.get("id") == musicbrainz_id:
                track = track_item
                break
        if track:
            recording_id = track.get("id")
            title = track.get("title")
            length = track.get("length")
            formatted_length = None
            if length:
                minutes, seconds = divmod(length // 1000, 60)
                formatted_length = f"{minutes}:{seconds:02d}"
            tags = [tag["name"] for tag in musicbrainz_data.get("tags", [])]
            is_valid = True

        query = """
            UPDATE tracks
            SET recording_id = %s,
                title = %s,
                length = %s,
                is_musicbrainz_valid = %s
            WHERE track_id = %s;
        """
        execute_query(
            cursor, query, (recording_id, title, formatted_length, is_valid, track_id)
        )

        # Update tags in the track_tags table
        if tags:
            update_track_tags(cursor, track_id, tags)
    else:
        # Mark as invalid if no data is available
        query = """
            UPDATE tracks
            SET is_musicbrainz_valid = FALSE
            WHERE track_id = %s;
        """
        execute_query(query, (track_id,))


def fetch_artist_tags(artist_id):
    """Fetch tags for an artist from MusicBrainz."""
    url = f"https://musicbrainz.org/ws/2/artist/{artist_id}"
    params = {"inc": "tags", "fmt": "json"}
    headers = {"User-Agent": "Paula/1.0 (susanna@example.com)"}

    response = requests.get(url, params=params, headers=headers)
    time.sleep(0.7)  # Respect API rate limit
    if response.status_code == 200:
        data = response.json()
        tags = [tag["name"] for tag in data.get("tags", [])]
        return tags
    else:
        logger.error(
            f"Error fetching tags for artist {artist_id}: {response.status_code}"
        )
        return []


def fetch_artist_relationships(artist_id):
    """Fetch relationships for an artist from MusicBrainz."""
    url = f"https://musicbrainz.org/ws/2/artist/{artist_id}"
    params = {"inc": "artist-rels", "fmt": "json"}
    headers = {"User-Agent": "Paula/1.0 (susanna@example.com)"}

    response = requests.get(url, params=params, headers=headers)
    time.sleep(0.7)  # Respect API rate limit
    if response.status_code == 200:
        data = response.json()
        relations = [
            {"related_artist_id": rel["artist"]["id"], "relationship_type": rel["type"]}
            for rel in data.get("relations", [])
            if "artist" in rel
        ]
        return relations
    else:
        logger.error(
            f"Error fetching relationships for artist {artist_id}: {response.status_code}"
        )
        return []


def update_artist_tags(cursor, artist_id, tags):
    """Update tags for an artist in the database."""
    # Remove existing tags
    execute_query(cursor, "DELETE FROM artist_tags WHERE artist_id = %s;", (artist_id,))

    # Insert new tags
    for tag in tags:
        execute_query(
            cursor,
            "INSERT INTO artist_tags (artist_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (artist_id, tag),
        )


def update_artist_relationships(cursor, artist_id, relationships):
    """Update relationships for an artist in the database."""
    # Remove existing relationships
    execute_query(
        cursor, "DELETE FROM artist_relationships WHERE artist_id = %s;", (artist_id,)
    )

    # Insert new relationships
    for relation in relationships:
        # Get related_artist_id from the database
        related_artist_id = get_artist_id_from_musicbrainz(
            cursor, relation["related_artist_id"]
        )
        if related_artist_id:
            execute_query(
                cursor,
                """
                INSERT INTO artist_relationships (artist_id, related_artist_id, relationship_type)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;
                """,
                (artist_id, related_artist_id, relation["relationship_type"]),
            )


def get_artist_id_from_musicbrainz(cursor, musicbrainz_artist_id):
    """Get artist ID from MusicBrainz ID in the database."""
    query = "SELECT artist_id FROM artists WHERE musicbrainz_artist_id = %s;"
    result = execute_query(cursor, query, (musicbrainz_artist_id,), fetch_one=True)
    return result[0] if result else None


def run_updater(scope):
    signal.signal(signal.SIGINT, signal_handler)
    """Run the MusicBrainz updater with CSV-based tracking and detailed logging."""
    logger.info("Starting MusicBrainz updater...")
    cursor = create_cursor()

    # Ensure the progress file is initialized
    initialize_progress_file(cursor)
    logger.info(f"Initialized or verified progress file: {PROGRESS_FILE}")

    # Fetch pending items
    pending_items = get_pending_items()
    total_items = len(pending_items)
    logger.info(f"Found {total_items} items to update.")

    for index, item in enumerate(pending_items, start=1):
        if stop_update:
            logger.info("Update stopped by user.")
            break

        entity_type = item["entity_type"]
        entity_id = int(item["entity_id"])
        musicbrainz_id = item["musicbrainz_id"]

        logger.info(
            f"Processing {entity_type} {index}/{total_items}: ID {entity_id}, MusicBrainz ID {musicbrainz_id}"
        )

        try:
            # Query MusicBrainz based on entity type
            if entity_type == "artist" and scope in ["artists", "all"]:
                data = query_musicbrainz("artist", musicbrainz_id)
                if data:
                    update_artist_metadata(cursor, entity_id, data)
                    logger.info(f"Successfully updated artist ID {entity_id}")
            elif entity_type == "album" and scope in ["albums", "all"]:
                data = query_musicbrainz(
                    "release", musicbrainz_id, includes="tags release-groups"
                )
                if data:
                    update_album_metadata(cursor, entity_id, data)
                    logger.info(f"Successfully updated album ID {entity_id}")
            elif entity_type == "track" and scope in ["tracks", "all"]:
                data = query_musicbrainz(
                    "release", f"?track={musicbrainz_id}", includes="tags"
                )
                if data:
                    update_track_metadata(cursor, entity_id, musicbrainz_id, data)
                    logger.info(f"Successfully updated track ID {entity_id}")

            commit()
            # Mark as updated
            update_item_status(entity_type, entity_id, "updated")
        except Exception as e:
            logger.error(f"Error updating {entity_type} ID {entity_id}: {e}")
            update_item_status(entity_type, entity_id, "error")

    close_cursor(cursor)
    close_connection()

    logger.info("MusicBrainz updater completed.")
