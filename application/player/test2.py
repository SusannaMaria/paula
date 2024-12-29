import math
import sys
import time
from typing import List
from pydub import AudioSegment


def graph_frames_from_audio(data, step, width, divisor):
    """
    Interpolates values in data list by taking an average of step values.
    After processing width * step values will yield a list of width
    interpolated values.
    Once the data array has been processed yields final list of the remaining
    values if there are any.

    :param data: array of numbers representing audio data
    :param step: number of values to use for interpolation
    :param width: width of frame, number of interpolated values
    :param divisor: divide each value with this number
    :return: generator yielding a current frame
    """
    point = 0
    current_sum = 0
    current_frame = []
    for x in data:
        current_sum += int((abs(x) // divisor))
        point += 1
        if point == step:
            current_frame.append(math.ceil(current_sum / point))
            point = 0
            current_sum = 0
        if len(current_frame) == width:
            yield current_frame
            current_frame = []
    if current_frame:
        yield current_frame
    elif current_sum:
        yield [current_sum / point]


def calc_data_for_visualization(
    data: List[float],
    frame_rate: int,
    max_amp: float,
    width: int,
    fps: int,
    height: int,
):
    """
    Calculates all the data we need to visualize audio stream
    """
    length = len(data)
    point_interval = frame_rate // (width * fps)  # interval used for interpolation
    if point_interval == 0:
        return
    frame_mod = length % (point_interval * width)
    last_frame_length = (
        frame_rate / (length % (point_interval * width)) if frame_mod != 0 else 1
    )
    interval = 1.0 / fps
    divisor = max_amp / height
    return length, point_interval, last_frame_length, interval, divisor


def print_frame(frame, height, print_char):
    """
    Prints print_char bars of height frame[x] where x is a position of
    the bar from left to right.

    :param frame: list of heights
    :param height: maximum height
    :param print_char: char used to represent a bar
    """
    for i in range(height, 0, -1):
        for j in range(len(frame)):
            if i <= frame[j]:
                print(print_char, end="")
            else:
                print(" ", end="")
        print()


def clear_frame(height):
    for _ in range(height):
        sys.stdout.write("\033[F\033[K")


def visualize(
    data,
    frame_rate: int,
    max_amp: float,
    fps=30,
    width=60,
    height=20,
    print_char="#",
    debug=False,
    sync=True,
):
    """
    Visualizes the data array

    :param data: array of numbers representing audio stream
    :param frame_rate: audio frame rate, number of values in the data array representing one second of audio
    :param max_amp: maximum amplitude of the audio data
    :param fps: how many frames to render each second
    :param width: width of rendered frames, 1 unit represents one char length in terminal
    :param height: height of rendered frames, 1 unit represents one char length in terminal
    :param print_char: char used to render frames
    :param debug: if true will print number of skipped frames
    :param sync: if true will keep the graphical representation in sync with audio, else will just print graphical
    frames as they are calculated
    :return: number of skipped frames
    """
    length, point_interval, last_frame_length, interval, divisor = (
        calc_data_for_visualization(data, frame_rate, max_amp, width, fps, height)
    )
    skipped_frames = 0
    audio_start = time.time()
    print_frame([0] * width, height, " ")
    for i, f in enumerate(
        graph_frames_from_audio(data, point_interval, width, divisor)
    ):
        clear_frame(height)
        print(f)
        # print_frame(f, height, print_char)
        frame_length = (
            last_frame_length if i == length - 1 else 1
        )  # 1 denotes full frame
        end_time = audio_start + (
            (i + 1 * frame_length) * interval
        )  # time at which we should print next frame
        sleep_for = end_time - time.time()
        if sync and sleep_for > 0:
            time.sleep(sleep_for)  # sleep till next frame
        else:
            skipped_frames += 1
    if debug:
        print(skipped_frames)
    return skipped_frames


audio = AudioSegment.from_file("/mnt/c/temp/test.flac")
data = audio.get_array_of_samples()[
    0::2
]  # in stereo audio there are two channels, we only want one
visualize(data, audio.frame_rate, audio.max_possible_amplitude)
