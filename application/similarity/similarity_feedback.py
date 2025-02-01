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

import curses

from application.database.database_helper import get_track_by_id


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
        curses.start_color()
        curses.curs_set(1)  # Enable cursor
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)  # Red text
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Green text
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Yellow text
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Blue text

        stdscr.clear()
        # Step 4: Display the text with different colors
        stdscr.addstr("For the track: ", curses.A_BOLD)

        # Track title in yellow
        stdscr.addstr(origin_track["track_title"], curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(" - ", curses.A_BOLD)

        # Artist name in green
        stdscr.addstr(origin_track["artist_name"], curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(" - ", curses.A_BOLD)

        # Album name in blue
        stdscr.addstr(origin_track["album_name"], curses.color_pair(3) | curses.A_BOLD)

        # Instructions
        stdscr.addstr("\n\nRate Tracks (1-5). Press 'q' to quit.\n", curses.A_BOLD)

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
                # Display "Track X:" and the other elements with colors
                stdscr.addstr(idx + 2, 0, f"Track {idx + 1}: ", curses.A_BOLD)
                stdscr.addstr(
                    title, curses.color_pair(1) | curses.A_BOLD
                )  # Title in yellow
                stdscr.addstr(" - ", curses.A_BOLD)
                stdscr.addstr(
                    artist, curses.color_pair(2) | curses.A_BOLD
                )  # Artist in green
                stdscr.addstr(" - ", curses.A_BOLD)
                stdscr.addstr(
                    album, curses.color_pair(3) | curses.A_BOLD
                )  # Album in blue
                stdscr.addstr(
                    f" (ID: {track_id})", curses.color_pair(4)
                )  # Track ID in cyan

                stdscr.addstr(" - Rating (1-5): ", curses.A_BOLD)
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
