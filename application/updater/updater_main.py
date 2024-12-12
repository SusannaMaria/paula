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

from logging import config
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
import time
import requests
import hashlib

logger = logging.getLogger(__name__)


PROGRESS_FILE = "update_progress.csv"

stop_update = False


# Signal handler for graceful interruption
def signal_handler(sig, frame):
    global stop_update
    logger.info("Stopping update after current file.")
    stop_update = True


def initialize_progress_file(cursor, filter_invalid=True):
    """Initialize the progress file if it doesn't exist."""
    if not os.path.exists(PROGRESS_FILE):
        entities = []

        # Conditionally add filter to queries
        condition = (
            ""
            if filter_invalid
            else "WHERE is_musicbrainz_valid IS FALSE OR is_musicbrainz_valid IS NULL"
        )

        # Fetch artists, albums, and tracks with MusicBrainz IDs
        for entity_type, query_template in [
            (
                "artist",
                "SELECT artist_id, musicbrainz_artist_id FROM artists {condition}",
            ),
            (
                "album",
                "SELECT album_id, musicbrainz_album_id FROM albums {condition}",
            ),
            (
                "track",
                "SELECT track_id, musicbrainz_release_track_id FROM tracks {condition}",
            ),
        ]:
            query = query_template.format(condition=condition)
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


def get_pending_items(retry_errors):
    """Retrieve pending items from the progress file."""
    pending_items = []
    if retry_errors:
        status = "error"
    else:
        status = "pending"

    with open(PROGRESS_FILE, mode="r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:

            if row["status"] == status:
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

    params = {"fmt": "json"}
    if includes:
        params["inc"] = includes
    url = f"{entity_type}/{mbid}"

    try:
        return fetch_with_retries(url, params)
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

        wikidata_url = next(
            (
                rel["url"]
                for rel in musicbrainz_data.get("relations", [])
                if "wikidata" in rel.get("type", "")
            ),
            None,
        )
        wikidata_id = None
        if wikidata_url:
            if wikidata_url["resource"]:
                wikidata_id = wikidata_url["resource"].split("/")[
                    -1
                ]  # Extract the ID from the URL
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
                is_musicbrainz_valid = %s,
                wikidata_id = %s
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
                wikidata_id,
                artist_id,
            ),
        )
        if wikidata_id:
            image_url = get_artist_image_from_wikidata(wikidata_id)
            if image_url:
                download_image_to_artist_folder(image_url, wikidata_id)
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


def insert_track_features(cursor, track_id, features):
    """
    Insert or replace features for a track in the track_features table.
    Deletes existing features for the given track_id before inserting new ones.

    Args:
        cursor: Database cursor.
        track_id (int): ID of the track.
        features (dict): Extracted feature values to insert.
    """
    # Delete existing entry for the track_id
    delete_query = "DELETE FROM track_features WHERE track_id = %s;"
    cursor.execute(delete_query, (track_id,))

    # Insert new features
    insert_query = """
    INSERT INTO track_features (
        track_id, danceability, female, male, genre_alternative, genre_blues, 
        genre_electronic, genre_folkcountry, genre_funksoulrnb, genre_jazz, 
        genre_pop, genre_raphiphop, genre_rock, genre_electronic_ambient, 
        genre_electronic_dnb, genre_electronic_house, genre_electronic_techno, 
        genre_electronic_trance, genre_rosamerica_cla, genre_rosamerica_dan, 
        genre_rosamerica_hip, genre_rosamerica_jaz, genre_rosamerica_pop, 
        genre_rosamerica_rhy, genre_rosamerica_roc, genre_rosamerica_spe, 
        genre_tzanetakis_blu, genre_tzanetakis, genre_tzanetakis_cou, 
        genre_tzanetakis_dis, genre_tzanetakis_hip, genre_tzanetakis_jaz, 
        genre_tzanetakis_met, genre_tzanetakis_pop, genre_tzanetakis_reg, 
        genre_tzanetakis_roc, ismir04_rhythm_ChaChaCha, ismir04_rhythm_Jive, 
        ismir04_rhythm_Quickstep, ismir04_rhythm_Rumba_American, 
        ismir04_rhythm_Rumba_International, ismir04_rhythm_Rumba_Misc, 
        ismir04_rhythm_Samba, ismir04_rhythm_Tango, ismir04_rhythm_VienneseWaltz, 
        ismir04_rhythm_Waltz, mood_acoustic, mood_electronic, mood_happy, 
        mood_party, mood_relaxed, mood_sad, moods_mirex, timbre, tonal_atonal, 
        voice_instrumental, average_loudness, dynamic_complexity, bpm, 
        chords_key, chords_number_rate, chords_scale, danceability_low
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s,%s,%s,%s)
    """
    cursor.execute(
        insert_query, [track_id] + [features.get(key) for key in features.keys()]
    )


def update_track_metadata(cursor, track_id, musicbrainz_id, musicbrainz_data):
    """Update track metadata and tags in the database."""
    if musicbrainz_data:
        # Extract and update fields
        track = None
        for media in musicbrainz_data["releases"][0]["media"]:
            for track_item in media["tracks"]:
                if track_item.get("id") == musicbrainz_id:
                    track = track_item
                    break
            if track:
                break

        if track and "recording" in track:
            # print(track)
            recording_id = track["recording"].get("id")
            title = track["recording"].get("title")
            length = track["recording"].get("length")
            formatted_length = None
            if length:
                minutes, seconds = divmod(length // 1000, 60)
                formatted_length = f"{minutes}:{seconds:02d}"
            tags = [tag["name"] for tag in musicbrainz_data.get("tags", [])]
            is_valid = True
            update_track_metadata_with_acousticbrainz(cursor, track_id, recording_id)

            query = """
                UPDATE tracks
                SET recording_id = %s,
                    title = %s,
                    length = %s,
                    is_musicbrainz_valid = %s
                WHERE track_id = %s;
            """
            execute_query(
                cursor,
                query,
                (recording_id, title, formatted_length, is_valid, track_id),
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
    url = f"artist/{artist_id}"
    params = {"inc": "tags", "fmt": "json"}
    data = fetch_with_retries(url, params)

    if data:
        tags = [tag["name"] for tag in data.get("tags", [])]
        return tags
    else:
        logger.error(f"Error fetching tags for artist {artist_id}")
        return []


def fetch_artist_relationships(artist_id):
    """Fetch relationships for an artist from MusicBrainz."""
    url = f"artist/{artist_id}"
    params = {"inc": "artist-rels", "fmt": "json"}
    data = fetch_with_retries(url, params)
    if data:
        relations = [
            {"related_artist_id": rel["artist"]["id"], "relationship_type": rel["type"]}
            for rel in data.get("relations", [])
            if "artist" in rel
        ]
        return relations
    else:
        logger.error(f"Error fetching relationships for artist {artist_id}")
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


def fetch_with_retries(
    suburl,
    params=None,
    base_url="https://musicbrainz.org/ws/2",
    max_retries=5,
    backoff_factor=1,
):
    """
    Fetch data from a URL with retry logic for 503 errors.

    Args:
        url (str): The URL to fetch.
        params (dict): Query parameters.
        headers (dict): Request headers.
        max_retries (int): Maximum number of retries.
        backoff_factor (int): Factor for exponential backoff.

    Returns:
        Response: The HTTP response object if successful.
        None: If all retries fail.
    """
    headers = config["musicbrainz"]["headers"]
    url = f"{base_url}/{suburl}"
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
            time.sleep(0.5)
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 503 or response.status_code == 429:
                wait_time = backoff_factor * (2 ** (attempt - 1))  # Exponential backoff
                logger.info(
                    f"Attempt {attempt}/{max_retries} failed with {response.status_code}. Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"HTTP error occurred: {e}")
                break
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            break

    logger.error(f"Failed to fetch data from {url} after {max_retries} attempts.")
    return None


def fetch_and_update_wikidata_id(artist_id, musicbrainz_artist_id):
    """Fetch Wikidata ID for an artist and update the database."""
    url = f"https://musicbrainz.org/ws/2/artist/{musicbrainz_artist_id}?inc=url-rels&fmt=json"
    headers = config["musicbrainz"]["headers"]
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        wikidata_url = next(
            (
                rel["target"]
                for rel in data.get("relations", [])
                if "wikidata.org" in rel.get("target", "")
            ),
            None,
        )
        if wikidata_url:
            wikidata_id = wikidata_url.split("/")[-1]  # Extract the ID from the URL
            query = "UPDATE artists SET wikidata_id = %s WHERE artist_id = %s;"
            execute_query(query, (wikidata_id, artist_id))
            logger.info(f"Updated Wikidata ID for artist {artist_id}: {wikidata_id}")


def process_entity(
    entity_type, index, total_items, entity_id, musicbrainz_id, scope, cursor
):
    """Process a single entity (artist, album, or track) based on its type."""
    entity_config = {
        "artist": {
            "scope_check": "artists",
            "query_type": "artist",
            "includes": "url-rels",
            "id_format": lambda mb_id: mb_id,  # Use musicbrainz_id directly
            "update_func": lambda cursor, entity_id, data: update_artist_metadata(
                cursor, entity_id, data
            ),
            "success_log": f"Successfully updated artist ID {entity_id}",
        },
        "album": {
            "scope_check": "albums",
            "query_type": "release",
            "includes": "tags release-groups",
            "id_format": lambda mb_id: mb_id,  # Use musicbrainz_id directly
            "update_func": lambda cursor, entity_id, data: update_album_metadata(
                cursor, entity_id, data
            ),
            "success_log": f"Successfully updated album ID {entity_id}",
        },
        "track": {
            "scope_check": "tracks",
            "query_type": "release",
            "includes": "tags",
            "id_format": lambda mb_id: f"?track={mb_id}",  # Format for track queries
            "update_func": lambda cursor, entity_id, data: update_track_metadata(
                cursor, entity_id, musicbrainz_id, data
            ),
            "success_log": f"Successfully updated track ID {entity_id}",
        },
    }

    if entity_type not in entity_config:
        logger.error(f"Unknown entity type: {entity_type}")
        return

    config = entity_config[entity_type]

    if scope in [config["scope_check"], "all"]:
        logger.info(
            f"Processing {entity_type} {index}/{total_items}: "
            f"ID {entity_id}, MusicBrainz ID {musicbrainz_id}"
        )

        # Query MusicBrainz
        try:
            formatted_id = config["id_format"](musicbrainz_id)
            query_params = config["includes"]
            data = query_musicbrainz(
                config["query_type"], formatted_id, includes=query_params
            )
        except Exception as e:
            logger.error(
                f"Failed to query MusicBrainz for {entity_type} ID {entity_id}: {e}"
            )
            update_item_status(entity_type, entity_id, "error")
            return

        if data:
            try:
                # Update the database
                config["update_func"](cursor, entity_id, data)
                logger.info(config["success_log"])
                commit()

                # Mark as updated
                update_item_status(entity_type, entity_id, "updated")
            except Exception as e:
                logger.error(f"Failed to update {entity_type} ID {entity_id}: {e}")
                update_item_status(entity_type, entity_id, "error")
        else:
            logger.warning(f"No data found for {entity_type} ID {entity_id}")
            update_item_status(entity_type, entity_id, "no_data")


def fetch_wikidata_image(wikidata_id):
    """Fetch the image filename from Wikidata for the given ID."""
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
    headers = config["musicbrainz"]["headers"]
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Navigate to the P18 property in the JSON data
        claims = data["entities"][wikidata_id]["claims"]
        image_filename = (
            claims.get("P18", [{}])[0]
            .get("mainsnak", {})
            .get("datavalue", {})
            .get("value")
        )
        return image_filename
    except Exception as e:
        logger.error(f"Error fetching image for Wikidata ID {wikidata_id}: {e}")
        return None


def construct_commons_url(image_filename):
    """Construct the Wikimedia Commons URL for the given image filename."""
    image_filename = image_filename.replace(" ", "_")
    name_hash = hashlib.md5(image_filename.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{name_hash[0]}/{name_hash[0:2]}/{image_filename}"


def get_artist_image_from_wikidata(wikidata_id):
    """Fetch and construct the image URL for an artist from Wikidata."""
    image_filename = fetch_wikidata_image(wikidata_id)
    if image_filename:
        image_url = construct_commons_url(image_filename)
        logger.info(f"Image URL for Wikidata ID {wikidata_id}: {image_url}")
        return image_url
    else:
        logger.error(f"No image found for Wikidata ID {wikidata_id}.")
        return None


def download_image_to_artist_folder(url, artist_name, base_folder="artists"):
    """
    Downloads an image from a URL and stores it in the specified artist's folder.

    Args:
        url (str): The URL of the image to download.
        artist_name (str): The name of the artist (used for the folder).
        base_folder (str): The base folder where artist folders are created.

    Returns:
        str: Path to the saved image, or None if download failed.
    """
    try:
        # Create the artist's folder if it doesn't exist
        artist_folder = os.path.join(base_folder, artist_name.replace(" ", "_"))
        os.makedirs(artist_folder, exist_ok=True)
        headers = config["musicbrainz"]["headers"]
        # Get the image content from the URL
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()  # Raise an error for HTTP issues

        # Determine the image's filename
        filename = os.path.basename(url)
        file_path = os.path.join(artist_folder, filename)

        # Save the image to the artist's folder
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)

        logger.info(f"Image successfully saved to {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None


def extract_acousticbrainz_features_low(data):
    features = {
        "average_loudness": data.get("lowlevel", {}).get("average_loudness"),
        "dynamic_complexity": data.get("lowlevel", {}).get("dynamic_complexity"),
        "bpm": data.get("rhythm", {}).get("bpm"),
        "chords_key": data.get("tonal", {}).get("chords_key"),
        "chords_number_rate": data.get("tonal", {}).get("chords_number_rate"),
        "chords_scale": data.get("tonal", {}).get("chords_scale"),
        "danceability_low": data.get("rhythm", {}).get("danceability"),
    }
    return features


def extract_acousticbrainz_features_high(data):
    """
    Extract relevant features from AcousticBrainz data.

    Args:
        data (dict): AcousticBrainz response JSON.

    Returns:
        dict: Extracted features.
    """
    features = {
        "danceability": data.get("danceability", {}).get("all", {}).get("danceable"),
        "female": data.get("gender", {}).get("all", {}).get("female"),
        "male": data.get("gender", {}).get("all", {}).get("male"),
        "genre_alternative": data.get("genre_dortmund", {})
        .get("all", {})
        .get("alternative"),
        "genre_blues": data.get("genre_dortmund", {}).get("all", {}).get("blues"),
        "genre_electronic": data.get("genre_dortmund", {})
        .get("all", {})
        .get("electronic"),
        "genre_folkcountry": data.get("genre_dortmund", {})
        .get("all", {})
        .get("folkcountry"),
        "genre_funksoulrnb": data.get("genre_dortmund", {})
        .get("all", {})
        .get("funksoulrnb"),
        "genre_jazz": data.get("genre_dortmund", {}).get("all", {}).get("jazz"),
        "genre_pop": data.get("genre_dortmund", {}).get("all", {}).get("pop"),
        "genre_raphiphop": data.get("genre_dortmund", {})
        .get("all", {})
        .get("raphiphop"),
        "genre_rock": data.get("genre_dortmund", {}).get("all", {}).get("rock"),
        "genre_electronic_ambient": data.get("genre_electronic", {})
        .get("all", {})
        .get("ambient"),
        "genre_electronic_dnb": data.get("genre_electronic", {})
        .get("all", {})
        .get("dnb"),
        "genre_electronic_house": data.get("genre_electronic", {})
        .get("all", {})
        .get("house"),
        "genre_electronic_techno": data.get("genre_electronic", {})
        .get("all", {})
        .get("techno"),
        "genre_electronic_trance": data.get("genre_electronic", {})
        .get("all", {})
        .get("trance"),
        "genre_rosamerica_cla": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("cla"),
        "genre_rosamerica_dan": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("dan"),
        "genre_rosamerica_hip": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("hip"),
        "genre_rosamerica_jaz": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("jaz"),
        "genre_rosamerica_pop": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("pop"),
        "genre_rosamerica_rhy": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("rhy"),
        "genre_rosamerica_roc": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("roc"),
        "genre_rosamerica_spe": data.get("genre_rosamerica", {})
        .get("all", {})
        .get("spe"),
        "genre_tzanetakis_blu": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("blu"),
        "genre_tzanetakis": data.get("genre_tzanetakis", {}).get("all", {}).get("cla"),
        "genre_tzanetakis_cou": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("cou"),
        "genre_tzanetakis_dis": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("dis"),
        "genre_tzanetakis_hip": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("hip"),
        "genre_tzanetakis_jaz": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("jaz"),
        "genre_tzanetakis_met": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("met"),
        "genre_tzanetakis_pop": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("pop"),
        "genre_tzanetakis_reg": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("reg"),
        "genre_tzanetakis_roc": data.get("genre_tzanetakis", {})
        .get("all", {})
        .get("roc"),
        "ismir04_rhythm_ChaChaCha": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("ChaChaCha"),
        "ismir04_rhythm_Jive": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Jive"),
        "ismir04_rhythm_Quickstep": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Quickstep"),
        "ismir04_rhythm_Rumba_American": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Rumba-American"),
        "ismir04_rhythm_Rumba_International": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Rumba-International"),
        "ismir04_rhythm_Rumba_Misc": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Rumba-Misc"),
        "ismir04_rhythm_Samba": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Samba"),
        "ismir04_rhythm_Tango": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Tango"),
        "ismir04_rhythm_VienneseWaltz": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("VienneseWaltz"),
        "ismir04_rhythm_Waltz": data.get("ismir04_rhythm", {})
        .get("all", {})
        .get("Waltz"),
        "mood_acoustic": data.get("mood_acoustic", {}).get("all", {}).get("acoustic"),
        "mood_electronic": data.get("mood_electronic", {})
        .get("all", {})
        .get("electronic"),
        "mood_happy": data.get("mood_happy", {}).get("all", {}).get("happy"),
        "mood_party": data.get("mood_party", {}).get("all", {}).get("party"),
        "mood_relaxed": data.get("mood_relaxed", {}).get("all", {}).get("relaxed"),
        "mood_sad": data.get("mood_sad", {}).get("all", {}).get("sad"),
        "moods_mirex": data.get("moods_mirex", {}).get("all", {}).get("mirex"),
        "timbre": data.get("timbre", {}).get("all", {}).get("bright"),
        "tonal_atonal": data.get("tonal_atonal", {}).get("all", {}).get("atonal"),
        "voice_instrumental": data.get("voice_instrumental", {})
        .get("all", {})
        .get("instrumental"),
    }
    return features


def fetch_acousticbrainz_data_high(recording_id):
    """Fetch AcousticBrainz data for a given recording ID."""
    url = f"https://acousticbrainz.org/{recording_id}"
    try:
        data = fetch_with_retries("high-level", None, url)
        features = extract_acousticbrainz_features_high(data.get("highlevel", {}))
        return features
    except Exception as e:
        logger.error(f"Error fetching AcousticBrainz data for {recording_id}: {e}")
        return None


def fetch_acousticbrainz_data_low(recording_id):
    """Fetch AcousticBrainz data for a given recording ID."""
    url = f"https://acousticbrainz.org/{recording_id}"
    try:
        data = fetch_with_retries("low-level", None, url)
        features = extract_acousticbrainz_features_low(data)
        return features
    except Exception as e:
        logger.error(f"Error fetching AcousticBrainz data for {recording_id}: {e}")
        return None


def update_track_metadata_with_acousticbrainz(
    cursor, track_id, musicbrainz_release_track_id
):
    """Update track metadata with data from MusicBrainz and AcousticBrainz."""
    # Fetch AcousticBrainz data
    acousticbrainz_features_high = fetch_acousticbrainz_data_high(
        musicbrainz_release_track_id
    )
    acousticbrainz_features_low = fetch_acousticbrainz_data_low(
        musicbrainz_release_track_id
    )
    if acousticbrainz_features_high and acousticbrainz_features_low:
        acousticbrainz_features = (
            acousticbrainz_features_high | acousticbrainz_features_low
        )
        insert_track_features(cursor, track_id, acousticbrainz_features)


def run_updater(scope, retry_errors, update_valid_entries):
    """Run the MusicBrainz updater with CSV-based tracking and detailed logging."""
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Starting MusicBrainz updater...")
    cursor = create_cursor()

    # Ensure the progress file is initialized
    initialize_progress_file(cursor, update_valid_entries)
    logger.info(f"Initialized or verified progress file: {PROGRESS_FILE}")

    # Fetch pending items
    pending_items = get_pending_items(retry_errors)
    total_items = len(pending_items)
    logger.info(f"Found {total_items} items to update.")

    for index, item in enumerate(pending_items, start=1):
        if stop_update:
            logger.info("Update stopped by user.")
            break

        entity_type = item["entity_type"]
        entity_id = int(item["entity_id"])
        musicbrainz_id = item["musicbrainz_id"]

        process_entity(
            entity_type, index, total_items, entity_id, musicbrainz_id, scope, cursor
        )

    close_cursor(cursor)
    close_connection()

    logger.info("MusicBrainz updater completed.")
