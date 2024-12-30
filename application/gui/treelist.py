import logging
from gui.paula_screen import PaulaScreen
from gui.log_controller import LogController
import pygame
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget import Image as AutoImage
from textual.app import App

from typing import Iterable

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MusicDatabaseApp(App):
    """Textual App to display the MusicDatabaseWidget."""

    CSS_PATH = "treelist.tcss"

    def on_mount(self) -> None:
        self.log_controller = LogController()

        # Start with the Main Screen
        pygame.init()
        self.push_screen(PaulaScreen(self.log_controller))


if __name__ == "__main__":

    MusicDatabaseApp().run()
