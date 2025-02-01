"""
    Title: Music Collection Manager
    Description: A Python application to manage and enhance a personal music collection.
    Author: Susanna
    License: MIT License
    Created: 2025

    Copyright (c) 2025 Susanna Maria Hepp

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

import json
import logging
import os

import docker

from application.database.database_helper import execute_query

logger = logging.getLogger(__name__)


def get_tracks_without_features(cursor):
    query = """
    SELECT t.*
    FROM tracks t
    LEFT JOIN track_features tf ON t.id = tf.track_id
    WHERE tf.track_id IS NULL;
    """

    results = execute_query(cursor, query, fetchall=True)
    # Convert results to a list of dictionaries
    tracks_without_features = [dict(row) for row in results]
    return tracks_without_features


def run_essentia_extractor(input_file):
    logger.info(f"analyse {input_file}")
    # Initialize the Docker client
    client = docker.from_env()
    root, extension = os.path.splitext(input_file)
    if extension.lower() == ".mp3":
        target_file = "/tmp/test.mp3"
    elif extension.lower() == ".flac":
        target_file = "/tmp/test.flac"
    elif extension.lower() == ".m4a":
        target_file = "/tmp/test.m4a"
    else:
        logger.error(f"Not supported: {input_file}")
        exit()

    # Define the Docker image and command
    image = "ghcr.io/mgoltzsche/essentia:dev"
    command = [
        "essentia_streaming_extractor_music",
        target_file,  # Input file inside the container
        "-",  # Output to stdout
        "/etc/essentia/profile.yaml",
    ]
    # Bind mount the input file
    volumes = {input_file: {"bind": target_file, "mode": "ro"}}  # Read-only bind

    # Run the container
    try:
        container = client.containers.run(
            image,
            command,
            volumes=volumes,
            remove=True,  # Auto-remove the container
            stdout=True,
            stderr=False,
            mem_limit="4g",
        )

        # Decode the container output as JSON
        output = container.decode("utf-8")
        data = json.loads(output)  # Parse JSON data
        return data

    except docker.errors.ContainerError as e:
        logger.error(f"Container error: {e.stderr.decode('utf-8')}")
    except docker.errors.ImageNotFound:
        logger.error(f"Image '{image}' not found. Please pull the image first.")
    except docker.errors.APIError as e:
        logger.error(f"Docker API error: {e}")
    return None
