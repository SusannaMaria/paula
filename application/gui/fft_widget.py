import os

import numpy as np
from pydub import AudioSegment
from scipy.fft import fft, rfft, rfftfreq
from scipy.signal.windows import hann
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import Container, Horizontal
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Label

# Audio configuration
CHUNK = 2048  # or larger
RATE = 44100  # Sampling rate in Hz

# Frequency range to keep (in Hz)
LOW_CUTOFF = 80  # Lower frequency limit
HIGH_CUTOFF = 10000  # Upper frequency limit
BACKGROUND_COLOR = (0, 0, 0)  # Black
GREY = (32, 32, 32)  # Grey
RED = (255, 0, 0)  # Red
BLUE = (0, 0, 255)  # Blue
GREEN = (0, 255, 0)
MAX_HEIGHT = 7  # Maximum height of the bars in rows
MAX_SATURATION = 0.8
BAR_COUNT = 80


class FFTBar(Label):
    """A single bar in the FFT visualization."""

    BAR_CHARACTERS = {
        "block": "█",
        "circle": "●",
        "square": "■",
        "triangle": "▲",
        "shaded": "▓",
        "target": "◎",
        "circle_empty": "◍",
    }

    def __init__(self, style="block", **kwargs):
        super().__init__(**kwargs)
        self.bar_char = self.BAR_CHARACTERS.get(style, "█")  # Default to block

    def set_height(self, magnitude: float, max_height: int, index: int):
        """Update the height of the bar based on FFT magnitude."""
        # Normalize the magnitude to determine the height

        normalized_height = int(magnitude * MAX_HEIGHT)

        # Calculate the color intensity (e.g., 0-255 for RGB)
        intensity = int((magnitude / max_height) * 255)  # Scale to 0-255

        # Update the bar's text and apply color
        self.styles.color = self.calculate_color(
            magnitude, index
        )  # Inline style for dynamic coloring
        self.update(
            "\n" * (MAX_HEIGHT - normalized_height)
            + (self.bar_char + "\n") * (normalized_height + 1)
        )

    def calculate_color(self, normalized_height, bar_position):
        """Calculate dual gradient color."""
        # Horizontal gradient (Red to Blue)
        normalized_position = bar_position / (BAR_COUNT - 1)
        midpoint = 0.5  # Midpoint for Red → Green → Blue transition
        # Determine which gradient section the bar belongs to
        if normalized_position <= midpoint:
            # Red to Green
            section_position = normalized_position / midpoint
            gradient_r = int(RED[0] + (GREEN[0] - RED[0]) * section_position)
            gradient_g = int(RED[1] + (GREEN[1] - RED[1]) * section_position)
            gradient_b = int(RED[2] + (GREEN[2] - RED[2]) * section_position)
        else:
            # Green to Blue
            section_position = (normalized_position - midpoint) / (1 - midpoint)
            gradient_r = int(GREEN[0] + (BLUE[0] - GREEN[0]) * section_position)
            gradient_g = int(GREEN[1] + (BLUE[1] - GREEN[1]) * section_position)
            gradient_b = int(GREEN[2] + (BLUE[2] - GREEN[2]) * section_position)

        # Adjust height to cap maximum saturation
        adjusted_height = normalized_height * MAX_SATURATION

        # Blend the gradient with grey based on adjusted height
        blended_r = int(GREY[0] + (gradient_r - GREY[0]) * adjusted_height)
        blended_g = int(GREY[1] + (gradient_g - GREY[1]) * adjusted_height)
        blended_b = int(GREY[2] + (gradient_b - GREY[2]) * adjusted_height)
        return Color(blended_r, blended_g, blended_b)


class FFTVisualizer(Horizontal):
    """Widget to display real-time FFT visualization as bars."""

    def __init__(
        self,
        fft_data,
        bar_count=80,
        freq_labels=None,
        update_interval=0.01,
        chunk_size=8096,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.fft_data = fft_data
        self.freq_labels = freq_labels or []  # Frequency labels for each bar
        self.update_interval = update_interval
        self.chunk_size = chunk_size
        self.max_height = 20  # Max bar height
        self.bar_count = bar_count
        # Create FFTBar widgets
        self.bars = []  # Will hold the FFTBar widgets

    def on_mount(self):
        """Called when the FFTVisualizer is added to the app."""
        # Create and mount FFTBar widgets
        self.bars = [FFTBar() for _ in range(self.bar_count)]
        for bar in self.bars:
            self.mount(bar)

    def update_bars(self):
        """Update the heights of the bars based on FFT data."""
        max_magnitude = (
            max(
                self.fft_data,
            )
            or 1
        )  # Prevent division by zero
        for index, (bar, magnitude) in enumerate(
            zip(
                self.bars,
                self.fft_data,
            )
        ):
            normalized_height = magnitude / max_magnitude
            # bar.set_height(magnitude / max_magnitude, self.max_height, index)
            bar.set_height(normalized_height, self.max_height, index)


# Frequency weighting function (optional, for balancing perception)
def frequency_weighting(frequencies):
    """Apply weighting to frequencies to balance perceived loudness."""
    return 1 / (frequencies + 1)  # Example: higher frequencies get slightly boosted


class AudioVisualizerApp(App):
    """Textual application to visualize audio FFT in real time from a file."""

    CSS = """
    Screen {
        align: center middle;
    }
    """

    def __init__(
        self,
        audio_file,
        update_interval=0.01,
        chunk_size=8096,
        bar_count=BAR_COUNT,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.audio_file = audio_file
        self.update_interval = update_interval
        self.chunk_size = chunk_size
        self.fft_data = np.zeros(chunk_size // 2)
        self.audio_data = None
        self.timer = None
        self.current_position = 0
        self.bar_count = bar_count

    def compose(self):
        """Compose the layout of the app."""
        yield FFTVisualizer(
            self.fft_data,
            bar_count=self.bar_count,
            update_interval=self.update_interval,
            chunk_size=self.chunk_size,
        )
        yield Label("dskhkfh", id="stats_label")

    def on_mount(self):
        """Start processing the audio file and visualization timer."""
        self.load_audio_file()
        self.timer = self.set_interval(self.update_interval, self.update_fft)

    def load_audio_file(self):
        """Load the audio file and prepare it for processing."""
        try:
            # Load audio using pydub
            audio = AudioSegment.from_file(self.audio_file)
            self.audio_data = np.array(audio.get_array_of_samples())

            # Resample to match the desired rate if necessary
            if audio.frame_rate != RATE:
                audio = audio.set_frame_rate(RATE)
                self.audio_data = np.array(audio.get_array_of_samples())

        except Exception as e:
            self.exit(f"Error loading audio file: {e}")

    def restart_timer(self):
        """Restart the timer with the updated interval."""
        if self.timer:
            self.timer.stop()  # Cancel the existing timer
        self.timer = self.set_interval(
            self.update_interval, self.update_fft
        )  # Start a new timer

    def update_fft(self):
        """Update FFT data and refresh the visualization."""
        if self.audio_data is None or self.current_position + self.chunk_size > len(
            self.audio_data
        ):
            return

        # Get the next chunk of audio
        data_chunk = self.audio_data[
            self.current_position : self.current_position + self.chunk_size
        ]

        # Apply a Hann window to reduce spectral leakage
        window = hann(self.chunk_size)
        windowed_chunk = data_chunk * window

        # Compute FFT and map to frequencies
        fft_output = np.abs(rfft(windowed_chunk))
        fft_frequencies = rfftfreq(
            self.chunk_size, 1 / RATE
        )  # Frequencies corresponding to FFT bins

        # Apply frequency filtering
        mask = (fft_frequencies >= LOW_CUTOFF) & (fft_frequencies <= HIGH_CUTOFF)
        fft_filtered = np.zeros_like(fft_output)
        fft_filtered[mask] = fft_output[mask]  # Keep only frequencies within the range

        # Define logarithmic frequency bands
        bands = np.logspace(
            np.log10(LOW_CUTOFF), np.log10(HIGH_CUTOFF), self.bar_count + 1
        )
        aggregated_bands = np.zeros(self.bar_count)

        # Aggregate FFT amplitudes into the frequency bands
        for i in range(self.bar_count):
            band_mask = (fft_frequencies >= bands[i]) & (fft_frequencies < bands[i + 1])
            aggregated_bands[i] = np.sum(fft_filtered[band_mask])

        # Apply a threshold to ignore residual noise
        THRESHOLD = 0.01  # Adjust as needed
        aggregated_bands[aggregated_bands < THRESHOLD] = 0

        # Apply logarithmic scaling to aggregated bands
        LOG_SCALING_OFFSET = 1e-10  # Small value to prevent log(0)
        aggregated_bands = np.sqrt(aggregated_bands)

        # Normalize the aggregated values
        max_val = np.max(aggregated_bands) or 1  # Prevent division by zero
        aggregated_bands = aggregated_bands / max_val  # Scale to [0, 1]

        # Store aggregated data and frequency labels for visualization
        self.fft_data = aggregated_bands  # Use aggregated values for bars
        self.fft_freq_labels = [
            f"{int(bands[i])}-{int(bands[i+1])} Hz" for i in range(len(bands) - 1)
        ]  # Frequency labels for each bar

        # Update position for next chunk
        OVERLAP = self.chunk_size // 2  # 50% overlap
        self.current_position += OVERLAP

        # Refresh the visualizer widget
        fft_widget = self.query_one(FFTVisualizer)
        fft_widget.fft_data = self.fft_data
        fft_widget.freq_labels = (
            self.fft_freq_labels
        )  # Pass frequency labels to the widget
        fft_widget.update_interval = self.update_interval
        fft_widget.chunk_size = self.chunk_size
        fft_widget.update_bars()

        stats_label = self.query_one("#stats_label")

        stats = []
        stats.append(f"LOW_CUTOFF:{LOW_CUTOFF}")
        stats.append(f"HIGH_CUTOFF:{HIGH_CUTOFF}")
        stats.append(f"Timer interval:{self.update_interval}")
        stats.append(f"Chunk size:{self.chunk_size}")
        stats_label.update("\n".join(stats))

    def on_key(self, event):
        """Handle key presses for adjusting scanning speed."""
        global LOW_CUTOFF, HIGH_CUTOFF
        if event.key == "t":
            self.chunk_size = min(
                self.chunk_size * 2, 8192
            )  # Double chunk size (max 8192)
            print(f"CHUNK increased to {self.chunk_size}")
        elif event.key == "r":
            self.chunk_size = max(
                self.chunk_size // 2, 512
            )  # Halve chunk size (min 512)
            print(f"CHUNK decreased to {CHUNK}")
        elif event.key == "f":
            self.update_interval = max(self.update_interval - 0.01, 0.01)
            print(f"Update Interval decreased to {self.update_interval:.3f} s")
            self.restart_timer()
        elif event.key == "s":
            self.update_interval = min(self.update_interval + 0.01, 0.5)
            print(f"Update Interval increased to {self.update_interval:.3f} s")
            self.restart_timer()
        elif event.key == "j":  # Decrease LOW_CUTOFF
            LOW_CUTOFF = max(LOW_CUTOFF - 10, 20)
            print(f"Low Cutoff decreased to {LOW_CUTOFF} Hz")
        elif event.key == "k":  # Increase LOW_CUTOFF
            LOW_CUTOFF = min(LOW_CUTOFF + 10, HIGH_CUTOFF - 10)
            print(f"Low Cutoff increased to {LOW_CUTOFF} Hz")
        elif event.key == "u":  # Decrease HIGH_CUTOFF
            HIGH_CUTOFF = max(HIGH_CUTOFF - 10, LOW_CUTOFF + 10)
            print(f"High Cutoff decreased to {HIGH_CUTOFF} Hz")
        elif event.key == "i":  # Increase HIGH_CUTOFF
            HIGH_CUTOFF = min(HIGH_CUTOFF + 10, 20000)
            print(f"High Cutoff increased to {HIGH_CUTOFF} Hz")

    def on_shutdown(self):
        """Handle any shutdown tasks."""
        pass


# Run the application
if __name__ == "__main__":
    audio_file_path = "c:/temp/test2.mp3"  # Replace with your audio file path
    if not os.path.exists(audio_file_path):
        print(f"Audio file {audio_file_path} not found!")
    else:
        app = AudioVisualizerApp(audio_file_path)
        app.run()
