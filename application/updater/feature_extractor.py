import json
import sqlite3
import docker
import logging
from database.database_helper import execute_query

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
    # Initialize the Docker client
    client = docker.from_env()

    # Define the Docker image and command
    image = "ghcr.io/mgoltzsche/essentia:dev"
    command = [
        "essentia_streaming_extractor_music",
        "/tmp/test.flac",  # Input file inside the container
        "-",  # Output to stdout
        "/etc/essentia/profile.yaml",
    ]

    # Bind mount the input file
    volumes = {input_file: {"bind": "/tmp/test.flac", "mode": "ro"}}  # Read-only bind

    # Run the container
    try:
        container = client.containers.run(
            image,
            command,
            volumes=volumes,
            remove=True,  # Auto-remove the container
            stdout=True,
            stderr=False,
        )

        # Decode the container output as JSON
        output = container.decode("utf-8")
        data = json.loads(output)  # Parse JSON data
        return data

    except docker.errors.ContainerError as e:
        print(f"Container error: {e.stderr.decode('utf-8')}")
    except docker.errors.ImageNotFound:
        print(f"Image '{image}' not found. Please pull the image first.")
    except docker.errors.APIError as e:
        logger.error(f"Docker API error: {e}")
    return None


# file_path = r"/mnt/c/Musik/LIBRARY/100blumen/Hoffnung, halt’s Maul!/100blumen - Hoffnung halt's Maul! - 01 Ey, die Vögel.flac"

# run_essentia_extractor(file_path, "test.json")
