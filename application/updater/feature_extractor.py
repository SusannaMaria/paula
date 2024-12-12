import docker


def run_essentia_extractor(input_file, output_file):
    # Initialize the Docker client
    client = docker.from_env()

    # Define the Docker image and command
    image = "ghcr.io/mgoltzsche/essentia"
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

        # Capture output and save to file
        with open(output_file, "w") as f:
            f.write(container.decode("utf-8"))

        print(f"Extraction completed. Results saved to {output_file}")

    except docker.errors.ContainerError as e:
        print(f"Container error: {e.stderr.decode('utf-8')}")
    except docker.errors.ImageNotFound:
        print(f"Image '{image}' not found. Please pull the image first.")
    except docker.errors.APIError as e:
        print(f"Docker API error: {e}")


file_path = r"/mnt/c/Musik/LIBRARY/100blumen/Hoffnung, halt’s Maul!/100blumen - Hoffnung halt's Maul! - 01 Ey, die Vögel.flac"

run_essentia_extractor(file_path, "test.json")
