from datetime import datetime
import logging
import os

from importer.importer_main import extract_valid_uuids, get_tag
from database.database_helper import (
    close_connection,
    close_cursor,
    commit,
    create_cursor,
    execute_query,
    insert_album,
    insert_artist,
    insert_track,
)
import uuid
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3TimeStamp

logger = logging.getLogger(__name__)


def process_audio_file_flac(cursor, file_path):
    musicbrainz_tags = {}
    audio = FLAC(file_path)
    metadata = {}
    for tag in audio:
        if tag.startswith("musicbrainz_"):
            musicbrainz_tags[tag] = (
                audio[tag][0] if isinstance(audio[tag], list) else audio[tag]
            )
    metadata["artist"] = audio["artists"][0]
    metadata["tracknumber"] = f'{audio["tracknumber"][0]}/{audio["totaltracks"][0]}'
    metadata["album"] = audio["album"][0]
    metadata["barcode"] = audio.get("barcode", [None])[0]
    metadata["title"] = audio["title"][0]
    metadata["discnumber"] = audio["discnumber"][0]
    metadata["genre"] = audio.get("genre", ["Unknown Genre"])[0]
    metadata["musicbrainz_album_id"] = musicbrainz_tags["musicbrainz_albumid"]
    metadata["musicbrainz_artist_id"] = musicbrainz_tags["musicbrainz_artistid"]
    metadata["musicbrainz_release_track_id"] = musicbrainz_tags[
        "musicbrainz_releasetrackid"
    ]
    metadata["musicbrainz_release_id"] = musicbrainz_tags["musicbrainz_releasegroupid"]
    metadata["release_date"] = audio["date"][0]
    metadata["length"] = f"{int(audio.info.length // 60)}:{int(audio.info.length % 60)}"
    metadata["path"] = file_path

    return metadata


def process_audio_file_mp3(cursor, file_path):
    musicbrainz_tags = {}
    audio = MP3(file_path)
    metadata = ID3(file_path)
    for frame in audio.keys():
        if frame.startswith("TXXX:MusicBrainz"):
            musicbrainz_tags[frame.replace("TXXX:", "")] = audio[frame].text[0]
    metadata_result = {}

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

    metadata_result["title"] = track_title
    metadata_result["album"] = album_name
    metadata_result["artist"] = artist_name
    metadata_result["genre"] = genre
    metadata_result["tracknumber"] = track_number

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

    metadata_result["release_date"] = year
    metadata_result["length"] = (
        f"{int(audio.info.length // 60)}:{int(audio.info.length % 60)}",
    )[0]

    metadata_result["barcode"] = get_tag(metadata, "TXXX:BARCODE")

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

    musicbrainz_release_id = get_tag(
        metadata, "TXXX:MusicBrainz Release Group Id"
    ) or musicbrainz_tags.get("musicbrainz_releaseid")

    metadata_result["musicbrainz_album_id"] = musicbrainz_album_id
    metadata_result["musicbrainz_artist_id"] = musicbrainz_artist_id
    metadata_result["musicbrainz_release_track_id"] = musicbrainz_release_track_id
    metadata_result["musicbrainz_release_id"] = musicbrainz_release_id
    metadata_result["path"] = file_path
    return metadata_result


def process_audio_file_m4a(cursor, file_path):
    logger.debug(f"Processing: {file_path}")

    try:
        audio = MP4(file_path)
        metadata = {
            "musicbrainz_release_track_id": str(
                audio.tags.get("----:com.apple.iTunes:MusicBrainz Track Id", [None])[
                    0
                ].decode("utf-8")
            ),
            "musicbrainz_release_id": str(
                audio.tags.get(
                    "----:com.apple.iTunes:MusicBrainz Release Group Id", [None]
                )[0].decode("utf-8")
            ),
            "musicbrainz_artist_id": str(
                audio.tags.get(
                    "----:com.apple.iTunes:MusicBrainz Album Artist Id", [None]
                )[0].decode("utf-8")
            ),
            "musicbrainz_album_id": str(
                audio.tags.get("----:com.apple.iTunes:MusicBrainz Album Id", [None])[
                    0
                ].decode("utf-8")
            ),
            "barcode": audio.tags.get("----:com.apple.iTunes:BARCODE", [None])[0],
            "title": audio.tags.get("©nam", [None])[0],
            "album": audio.tags.get("©alb", [None])[0],
            "artist": audio.tags.get("aART", [None])[0],
            "genre": audio.tags.get("©gen", [None])[0],  # Genre
            "tracknumber": audio.tags.get("trkn", [(None, None)])[0][
                0
            ],  # (track_number, total_tracks)
            "discnumber": audio.tags.get("disk", [(None, None)])[0][
                0
            ],  # (disk_number, total_disks)
            "release_date": audio.tags.get("©day", [None])[0],  # Release date
            "length": f"{int(audio.info.length // 60)}:{int(audio.info.length % 60)}",
            "path": file_path,
        }
        return metadata
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
    return None


def path_exists_in_tracks(cursor, file_path: str) -> bool:
    """Check if a specific file path exists in the tracks table."""
    track_id = execute_query(
        cursor,
        "SELECT track_id FROM tracks WHERE path = ?",
        (file_path,),
        fetch_one=True,
    )
    if track_id:
        return True
    return False


def scan_filesystem(directory, cursor):
    """Recursively scan the filesystem for audio files."""
    extensions = (".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a")
    metadatas = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(extensions):
                audio_file = os.path.join(root, file)
                if not path_exists_in_tracks(cursor, audio_file):
                    logger.debug(f"Missing track in db: {audio_file}")
                    if file.lower().endswith(".m4a"):
                        metadata = process_audio_file_m4a(cursor, audio_file)
                    elif file.lower().endswith(".mp3"):
                        metadata = process_audio_file_mp3(cursor, audio_file)
                    elif file.lower().endswith(".flac"):
                        metadata = process_audio_file_flac(cursor, audio_file)
                    else:
                        continue
                    metadatas.append(metadata)
    return metadatas


def process_track_entry(cursor, metadata):
    new_track_mb_id = None
    new_artist_mb_id = None
    new_album_mb_id = None

    SQL = "SELECT musicbrainz_release_track_id, path FROM tracks where musicbrainz_release_track_id = ?"
    track_id = execute_query(
        cursor,
        SQL,
        (metadata.get("musicbrainz_release_track_id"),),
        fetch_one=True,
    )
    # Files are duplicated!
    if track_id:
        logger.info(
            f'Duplicated entry, will be ignored. {track_id[1]} - {metadata.get("title")} - {metadata.get("artist")} - {metadata.get("album")} - {metadata.get("path")}'
        )
    else:
        new_track_mb_id = metadata.get("musicbrainz_release_track_id")
        # check Artist Entry
        SQL = "select artist_id,name from artists where musicbrainz_artist_id = ?"
        artist = execute_query(
            cursor,
            SQL,
            (metadata.get("musicbrainz_artist_id"),),
            fetch_one=True,
        )
        if not artist:
            new_artist_mb_id = metadata.get("musicbrainz_artist_id")
        else:
            logger.info(f'Artist found, {artist[1]} - {metadata.get("artist")}')
            artist_id = artist[0]

        # check Artist Entry
        SQL = "select album_id,name from albums where musicbrainz_album_id = ?"
        album = execute_query(
            cursor,
            SQL,
            (metadata.get("musicbrainz_album_id"),),
            fetch_one=True,
        )
        if not album:
            new_album_mb_id = metadata.get("musicbrainz_album_id")
        else:
            logger.info(f'Album found, {album[1]} - {metadata.get("album")}')
            album_id = album[0]

    if new_artist_mb_id:
        artist_id = insert_artist(cursor, metadata["artist"], new_artist_mb_id, True)
        logger.info(f'Artist added: {metadata["artist"]}')

    if new_album_mb_id:
        album_id = insert_album(
            cursor,
            metadata["album"],
            artist_id,
            new_album_mb_id,
            metadata["barcode"],
            metadata["release_date"],
            True,
            os.path.dirname(metadata["path"]),
        )
        logger.info(f'Album added: {metadata["album"]}')
    if new_track_mb_id:
        track_id = insert_track(
            cursor,
            metadata["title"],
            artist_id,
            album_id,
            metadata["genre"],
            metadata["release_date"],
            metadata["tracknumber"],
            metadata["path"],
            new_track_mb_id,
            True,
            metadata["length"],
        )
        if track_id:
            logger.info(f'Track added: {metadata["title"]}')
    if new_artist_mb_id or new_album_mb_id or new_track_mb_id:
        commit()


def update_database_with_audiofiles(directory):
    cursor = create_cursor()
    metadatas = scan_filesystem(directory, cursor)
    for metadata in metadatas:
        process_track_entry(cursor, metadata)

    close_cursor(cursor)
    close_connection()
