import curses
import json

from database.database_helper import get_track_by_id


def display_tracks_and_collect_feedback(cursor, from_track_id, tracks):
    """
    Display tracks in a curses-based UI and collect ratings for each track.

    :param tracks: List of similar tracks (tuples: track_id, track_name).
    :return: Dictionary of track ratings {track_id: rating}.
    """

    ratings = {}
    ratings[from_track_id] = -1

    origin_track = get_track_by_id(cursor, from_track_id)

    def curses_ui(stdscr):
        curses.curs_set(1)  # Enable cursor
        stdscr.clear()
        stdscr.addstr(
            f'For the track: {origin_track["track_title"]} - {origin_track["artist_name"]} - {origin_track["album_name"]} \nRate Tracks (1-5). Press "q" to quit.\n\n',
            curses.A_BOLD,
        )

        for idx, track_id in enumerate(tracks):
            similar_track = get_track_by_id(cursor, track_id)
            title = (
                similar_track["track_title"][:17] + "..."
                if len(similar_track["track_title"]) > 20
                else similar_track["track_title"]
            )
            artist = (
                similar_track["artist_name"][:17] + "..."
                if len(similar_track["artist_name"]) > 20
                else similar_track["artist_name"]
            )
            album = (
                similar_track["album_name"][:17] + "..."
                if len(similar_track["album_name"]) > 20
                else similar_track["album_name"]
            )
            rating = None
            while True:
                stdscr.addstr(
                    idx + 2,
                    0,
                    f"Track {idx + 1}: {title}-{artist}-{album} (ID: {track_id}) - Rating (1-5): ",
                )
                curses.echo()
                user_input = stdscr.getstr().decode("utf-8")

                if user_input.lower() == "q":
                    stdscr.addstr(len(tracks) + 4, 0, "Exiting feedback collection...")
                    return

                try:
                    rating = int(user_input)
                    if 1 <= rating <= 5:
                        ratings[track_id] = rating
                        break
                    else:
                        stdscr.addstr(
                            len(tracks) + 4,
                            0,
                            "Invalid input! Please enter a number between 1 and 5.",
                        )
                except ValueError:
                    stdscr.addstr(
                        len(tracks) + 4,
                        0,
                        "Invalid input! Please enter a valid number.",
                    )

        stdscr.addstr(
            len(tracks) + 4, 0, "Feedback collection completed. Press any key to exit."
        )
        stdscr.getch()

    # Start the curses UI
    curses.wrapper(curses_ui)

    return ratings
