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
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from mutagen.flac import FLAC, Picture
import imghdr

from database.database_helper import (
    close_connection,
    close_cursor,
    create_cursor,
    execute_query,
)
from PIL import Image

logger = logging.getLogger(__name__)


def detect_image_format(image_data):
    """Detect the format of the image (e.g., jpeg, png)."""
    return imghdr.what(None, h=image_data)


def ensure_cover_in_folder(folder_path, remove_existing=False):
    """Ensure there is a cover image in the folder with the correct extension."""
    if not os.path.isdir(folder_path):
        logger.error(f"Invalid folder path: {folder_path}")
        return

    # Remove existing covers if the option is enabled
    if remove_existing:
        logger.debug(f"Removing existing covers in {folder_path}...")
        for ext in ["jpg", "jpeg", "png"]:
            existing_cover = os.path.join(folder_path, f"cover.{ext}")
            if os.path.exists(existing_cover):
                os.remove(existing_cover)
                logger.debug(f"Removed existing cover: {existing_cover}")
    else:
        # Check if a cover image already exists
        for ext in ["jpg", "jpeg", "png"]:
            existing_cover = os.path.join(folder_path, f"cover.{ext}")
            if os.path.exists(existing_cover):
                logger.debug(f"Cover already exists: {existing_cover}")
                return

    # Scan audio files for embedded cover art
    logger.debug(f"Checking audio files in {folder_path} for embedded cover art...")
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if file_path.lower().endswith((".mp3", ".flac")):
            cover_data = extract_cover_from_audio(file_path)
            if cover_data:
                # Detect image format
                image_format = detect_image_format(cover_data)
                if image_format in ["jpeg", "png"]:
                    extension = "jpg" if image_format == "jpeg" else "png"
                    cover_path = os.path.join(folder_path, f"cover.{extension}")
                    with open(cover_path, "wb") as f:
                        f.write(cover_data)
                    logger.info(f"Cover extracted and saved to: {cover_path}")
                else:
                    logger.error(f"Unsupported cover format found in {file_path}.")
                return

    print(f"No cover art found in {folder_path}.")


def extract_cover_from_audio(file_path):
    """Extract cover art from an audio file."""
    try:
        if file_path.lower().endswith(".mp3"):
            audio = MP3(file_path, ID3=ID3)
            for tag in audio.tags.values():
                if isinstance(tag, APIC):  # APIC = Attached Picture
                    return tag.data  # Return binary data of the cover
        elif file_path.lower().endswith(".flac"):
            audio = FLAC(file_path)
            for picture in audio.pictures:
                if isinstance(picture, Picture):
                    return picture.data  # Return binary data of the cover
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
    return None


def get_cover_path(folder_path):
    """Check for cover.png or cover.jpg in the folder and return the path."""
    for ext in ["png", "jpg"]:
        cover_path = os.path.join(folder_path, f"cover.{ext}")
        if os.path.exists(cover_path):
            return cover_path
    return None


def get_album_covers(perform_action=True, remove_existing=False):
    """Retrieve all album covers from the database."""
    cursor = create_cursor()
    query = "SELECT folder_path FROM albums WHERE folder_path IS NOT NULL;"
    results = execute_query(cursor, query, fetch_all=True)
    covers = []
    for row in results:
        folder_path = row[0]
        if perform_action:
            ensure_cover_in_folder(folder_path, remove_existing)

        cover_path = get_cover_path(folder_path)

        if cover_path and os.path.exists(cover_path):
            covers.append(cover_path)
        else:
            logger.error(f"Can not find: {folder_path}")
    close_cursor(cursor)
    close_connection()
    return covers


def create_mosaic(output_path="mosaic.jpg", tile_size=100, grid_size=(33, 33)):
    """Create a mosaic from album covers."""
    covers = get_album_covers(perform_action=False)

    if not covers:
        print("No album covers found.")
        return

    mosaic_width = grid_size[0] * tile_size
    mosaic_height = grid_size[1] * tile_size
    mosaic = Image.new("RGB", (mosaic_width, mosaic_height))

    for index, cover_path in enumerate(covers):
        if index >= grid_size[0] * grid_size[1]:
            break  # Limit to grid size

        try:
            cover = Image.open(cover_path)
            cover = cover.resize((tile_size, tile_size), Image.Resampling.LANCZOS)

            x = (index % grid_size[0]) * tile_size
            y = (index // grid_size[0]) * tile_size
            mosaic.paste(cover, (x, y))
        except Exception as e:
            logger.error(f"Error processing {cover_path}: {e}")

    mosaic.save(output_path)
    logger.info(f"Mosaic saved to {output_path}")
