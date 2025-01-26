import time
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from scipy.fft import rfft, rfftfreq
from scipy.signal.windows import hann
from textual.app import App
from textual.color import Color
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Footer, Label
from utils.config_loader import load_config


class FFTBar(Label):
    """A single bar in the FFT visualization."""

    def __init__(self, max_height=7, bar_count=80, style="block", **kwargs):
        super().__init__(**kwargs)
        config = load_config()
        bar_characters = config["visualizer"]["bar_characters"]
        self.bar_char = bar_characters.get(style, "█")  # Default to block
        self.low_color = config["visualizer"]["low_color"]
        self.mid_color = config["visualizer"]["mid_color"]
        self.high_color = config["visualizer"]["high_color"]
        self.ground_color = config["visualizer"]["ground_color"]
        self.max_saturation = config["visualizer"]["max_saturation"]
        self.current_height = -1
        self.bar_count = bar_count
        self.max_height = max_height

    def set_height(self, magnitude: float, max_height: int, index: int):
        """Update the height of the bar based on FFT magnitude."""
        # Normalize the magnitude to determine the height

        self.current_height = magnitude
        normalized_height = int(magnitude * self.max_height)

        # if magnitude < 0.1:
        #     self.styles.color = Color(10, 10, 10)
        # else:
        # Update the bar's text and apply color
        self.styles.color = self.calculate_color(
            magnitude, index
        )  # Inline style for dynamic coloring
        self.update(
            "\n" * (self.max_height - normalized_height)
            + (self.bar_char + "\n") * (normalized_height + 1)
        )

    def calculate_color(self, normalized_height, bar_position):
        """Calculate dual gradient color."""
        # Horizontal gradient (Red to Blue)
        normalized_position = bar_position / (self.bar_count - 1)
        midpoint = 0.5  # Midpoint for Red → Green → Blue transition
        # Determine which gradient section the bar belongs to
        if normalized_position <= midpoint:
            # Red to Green
            section_position = normalized_position / midpoint
            gradient_r = int(
                self.low_color[0]
                + (self.mid_color[0] - self.low_color[0]) * section_position
            )
            gradient_g = int(
                self.low_color[1]
                + (self.mid_color[1] - self.low_color[1]) * section_position
            )
            gradient_b = int(
                self.low_color[2]
                + (self.mid_color[2] - self.low_color[2]) * section_position
            )
        else:
            # Green to Blue
            section_position = (normalized_position - midpoint) / (1 - midpoint)
            gradient_r = int(
                self.mid_color[0]
                + (self.high_color[0] - self.mid_color[0]) * section_position
            )
            gradient_g = int(
                self.mid_color[1]
                + (self.high_color[1] - self.mid_color[1]) * section_position
            )
            gradient_b = int(
                self.mid_color[2]
                + (self.high_color[2] - self.mid_color[2]) * section_position
            )

        # Adjust height to cap maximum saturation
        adjusted_height = normalized_height * self.max_saturation

        # Blend the gradient with grey based on adjusted height
        blended_r = int(
            self.ground_color[0] + (gradient_r - self.ground_color[0]) * adjusted_height
        )
        blended_g = int(
            self.ground_color[1] + (gradient_g - self.ground_color[1]) * adjusted_height
        )
        blended_b = int(
            self.ground_color[2] + (gradient_b - self.ground_color[2]) * adjusted_height
        )
        return Color(blended_r, blended_g, blended_b)


class FFTVisualizer(Horizontal):
    """Widget to display real-time FFT visualization as bars."""

    def __init__(
        self,
        max_height,
        fft_data,
        bar_count=80,
        freq_labels=None,
        chunk_size=8096,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.fft_data = fft_data
        self.freq_labels = freq_labels or []  # Frequency labels for each bar
        self.chunk_size = chunk_size
        self.max_height = max_height  # Max bar height
        self.bar_count = bar_count
        # Create FFTBar widgets
        self.bars = []  # Will hold the FFTBar widgets
        self.diff_time = 0.0

    def on_mount(self):
        """Called when the FFTVisualizer is added to the app."""
        # Create and mount FFTBar widgets
        self.bars = [
            FFTBar(self.max_height, self.bar_count) for _ in range(self.bar_count)
        ]
        for bar in self.bars:
            self.mount(bar)

    def update_bars(self):
        start_time = time.time()
        """Update the heights of the bars based on FFT data."""
        max_magnitude = (
            max(
                self.fft_data,
            )
            or 1
        )  # Prevent division by zero
        tolerance = 0.01  # Only refresh if change is greater than this
        for index, (bar, magnitude) in enumerate(
            zip(
                self.bars,
                self.fft_data,
            )
        ):
            normalized_height = magnitude / max_magnitude
            if abs(bar.current_height - normalized_height) > tolerance:
                # bar.set_height(magnitude / max_magnitude, self.max_height, index)
                bar.set_height(normalized_height, self.max_height, index)
        self.diff_time = time.time() - start_time


class AudioVisualizer(Widget):
    """Textual application to visualize audio FFT in real time from a file."""

    def __init__(
        self,
        chunk_size,
        rate,
        bar_count,
        height,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.audio_file = None
        self.update_interval = 0.01
        self.chunk_size = chunk_size
        self.fft_data = np.zeros(chunk_size // 2)
        self.audio_data = None
        self.timer = None
        self.current_position = 0
        self.bar_count = bar_count
        self.height = height
        self.sample_rate = None
        self.audio_length = None
        self.rate = rate
        self.debug_label = False
        config = load_config()
        visualizer_config = config["visualizer"]
        self.noise_threshold = visualizer_config["noise_threshold"]
        self.max_saturation = visualizer_config["max_saturation"]
        self.low_cutoff = visualizer_config["low_cutoff"]
        self.high_cutoff = visualizer_config["high_cutoff"]
        self.scale = visualizer_config["scale"]
        self.visualizer_stats_label = None
        self.pause = False

    def compose(self):
        """Compose the layout of the app."""
        yield FFTVisualizer(
            self.height,
            self.fft_data,
            bar_count=self.bar_count,
            chunk_size=self.chunk_size,
        )
        if self.debug_label:
            self.visualizer_stats_label = Label("", id="visualizer_stats_label")
            yield self.visualizer_stats_label

    def visualize(self, audio_file=None):
        if audio_file:
            audio_file_path = Path(audio_file)
            if audio_file_path.exists():
                self.audio_file = audio_file
            self.load_audio_file()

    def pause_resume(self, state):
        self.pause = state

    def load_audio_file(self):
        """Load the audio file and prepare it for processing."""
        try:
            audio_file_path = Path(self.audio_file)

            if not audio_file_path.exists():
                return
            # Load audio using pydub
            audio = AudioSegment.from_file(self.audio_file)

            # Ensure a consistent sample rate (e.g., 44100 Hz)
            self.sample_rate = audio.frame_rate
            if audio.frame_rate != self.rate:
                audio = audio.set_frame_rate(self.rate)
                samples = np.array(audio.get_array_of_samples())
            else:
                # Convert audio to raw PCM data as a NumPy array
                samples = np.array(audio.get_array_of_samples())

            # Handle stereo audio (convert to mono if needed)
            if audio.channels == 2:  # Stereo
                samples = samples.reshape((-1, 2))  # Reshape into (n_samples, 2)
                samples = samples.mean(
                    axis=1
                )  # Average left and right channels for mono

            # Store audio data and calculate duration
            self.audio_data = samples / np.max(np.abs(samples))  # Normalize to [-1, 1]
            self.audio_length = len(self.audio_data) / self.sample_rate
            self.chunk_size / self.sample_rate
            self.update_interval = self.chunk_size / self.sample_rate
            self.current_position = int(self.sample_rate * 0.2)
            self.restart_timer()
            # Resample to match the desired rate if necessary

        except Exception as e:
            self.exit(f"Error loading audio file: {e}")

    def restart_timer(self):
        """Restart the timer with the updated interval."""
        if self.timer:
            self.timer.stop()  # Cancel the existing timer
        self.timer = self.set_interval(
            self.update_interval, self.update_fft
        )  # Start a new timer
        try:
            self.visualizer_stats_label = self.app.query_one("#visualizer_stats_label")
        except:
            pass

    def set_position(self, pos_seconds):
        self.current_position = pos_seconds * self.sample_rate

    def update_fft(self):
        start_time = time.time()
        """Update FFT data and refresh the visualization."""
        if self.audio_data is None or self.current_position + self.chunk_size > len(
            self.audio_data
        ):
            return

        if self.pause:
            return

        now = time.time()

        # Initialize the start time on the first update
        if not hasattr(self, "start_time"):
            self.start_time = now
            self.last_update_time = now

        replay_time = self.current_position / self.sample_rate
        elapsed_system_time = now - self.start_time
        # Calculate the time difference
        time_difference = replay_time - elapsed_system_time
        if time_difference > 0:
            time.sleep(time_difference)

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
            self.chunk_size, 1 / self.rate
        )  # Frequencies corresponding to FFT bins

        # Apply frequency filtering
        mask = (fft_frequencies >= self.low_cutoff) & (
            fft_frequencies <= self.high_cutoff
        )
        fft_filtered = np.zeros_like(fft_output)
        fft_filtered[mask] = fft_output[mask]  # Keep only frequencies within the range

        # Define logarithmic frequency bands
        bands = np.logspace(
            np.log10(self.low_cutoff), np.log10(self.high_cutoff), self.bar_count + 1
        )
        aggregated_bands = np.zeros(self.bar_count)

        # Aggregate FFT amplitudes into the frequency bands
        for i in range(self.bar_count):
            band_mask = (fft_frequencies >= bands[i]) & (fft_frequencies < bands[i + 1])
            aggregated_bands[i] = np.sum(fft_filtered[band_mask])

        # Apply a threshold to ignore residual noise

        aggregated_bands[aggregated_bands < self.noise_threshold] = 0

        # Apply logarithmic scaling to aggregated bands

        # Apply scaling based on user selection
        if self.scale == "log":
            aggregated_bands = np.log1p(aggregated_bands)  # Logarithmic scaling
        elif self.scale == "sqrt":
            aggregated_bands = np.sqrt(aggregated_bands)
        else:
            aggregated_bands = aggregated_bands

        # Normalize the aggregated values
        max_val = np.max(aggregated_bands) or 1  # Prevent division by zero
        aggregated_bands = aggregated_bands / max_val  # Scale to [0, 1]

        # Store aggregated data and frequency labels for visualization
        self.fft_data = aggregated_bands  # Use aggregated values for bars
        self.fft_freq_labels = [
            f"{int(bands[i])}-{int(bands[i+1])} Hz" for i in range(len(bands) - 1)
        ]  # Frequency labels for each bar

        self.current_position += self.chunk_size

        # Refresh the visualizer widget
        fft_widget = self.query_one(FFTVisualizer)
        fft_widget.fft_data = self.fft_data
        fft_widget.freq_labels = (
            self.fft_freq_labels
        )  # Pass frequency labels to the widget
        fft_widget.update_interval = self.update_interval
        fft_widget.chunk_size = self.chunk_size
        fft_widget.update_bars()

        if self.visualizer_stats_label:
            current_time_seconds = self.current_position / self.sample_rate
            stats = []
            sleepy = time.time() - (self.start_time + current_time_seconds)
            stats.append(f"LOW_CUTOFF:{self.low_cutoff}")
            stats.append(f"HIGH_CUTOFF:{self.high_cutoff}")
            stats.append(f"Timer interval:{self.update_interval:.2f}")
            stats.append(f"Chunk size:{self.chunk_size}")
            stats.append(f"Update compute time: {time.time() - start_time:.3f}s")
            stats.append(f"Update visual time: {fft_widget.diff_time:.3f}s")
            stats.append(f"Position: {current_time_seconds:.2f}")
            stats.append(f"Delta: {sleepy:.2f}")
            self.visualizer_stats_label.update("\n".join(stats))

    def on_key(self, event):
        """Handle key presses for adjusting scanning speed."""

        if event.key == "t":
            self.chunk_size = min(
                self.chunk_size * 2, 8192
            )  # Double chunk size (max 8192)
            print(f"CHUNK increased to {self.chunk_size}")
        elif event.key == "r":
            self.chunk_size = max(
                self.chunk_size // 2, 512
            )  # Halve chunk size (min 512)
            print(f"CHUNK decreased to {self.chunk_size}")
        elif event.key == "f":
            self.update_interval = max(self.update_interval - 0.01, 0.01)
            print(f"Update Interval decreased to {self.update_interval:.3f} s")
            self.restart_timer()
        elif event.key == "s":
            self.update_interval = min(self.update_interval + 0.01, 0.5)
            print(f"Update Interval increased to {self.update_interval:.3f} s")
            self.restart_timer()
        elif event.key == "j":  # Decrease self.low_cutoff
            self.low_cutoff = max(self.low_cutoff - 10, 20)
            print(f"Low Cutoff decreased to {self.low_cutoff} Hz")
        elif event.key == "k":  # Increase self.low_cutoff
            self.low_cutoff = min(self.low_cutoff + 10, self.high_cutoff - 10)
            print(f"Low Cutoff increased to {self.low_cutoff} Hz")
        elif event.key == "u":  # Decrease self.high_cutoff
            self.high_cutoff = max(self.high_cutoff - 10, self.low_cutoff + 10)
            print(f"High Cutoff decreased to {self.high_cutoff} Hz")
        elif event.key == "i":  # Increase self.high_cutoff
            self.high_cutoff = min(self.high_cutoff + 10, 20000)
            print(f"High Cutoff increased to {self.high_cutoff} Hz")

    def on_shutdown(self):
        """Handle any shutdown tasks."""
        pass


class MyTextualApp(App):
    """Main Textual app integrating the audio visualizer."""

    def __init__(
        self,
        audio_file,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.visualizer = AudioVisualizer(
            chunk_size=8096,
            rate=44100,
            bar_count=50,
            height=7,
        )
        self.audio_file = audio_file

    def compose(self):
        yield self.visualizer
        yield Footer()  # Add a footer for key bindings

    def on_mount(self):
        self.visualizer.visualize(self.audio_file)


# Run the application
if __name__ == "__main__":
    app = MyTextualApp("c:/temp/test2.mp3")
    app.run()
