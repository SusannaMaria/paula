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

import time

import pygame
import sounddevice as sd
from utils.config_loader import load_config


def get_sounddevices():
    devices = sd.query_devices()
    playback_devices = [d for d in devices if d["max_output_channels"] > 0]
    print("Available Playback Devices (SoundDevice):")
    list_devices = []
    for idx, device in enumerate(playback_devices):
        try:
            pygame.mixer.quit()
            pygame.mixer.init(devicename=device["name"])
            if device["name"] not in list_devices:
                list_devices.append(device["name"])
        except pygame.error:
            pass
    return list_devices


def set_sounddevice(sounddevice=None):
    if sounddevice and sounddevice in get_sounddevices():
        pygame.mixer.quit()
        pygame.mixer.init(sounddevice)
    else:
        config = load_config()
        sounddevice = config.setdefault("sounddevice", None)
        if sounddevice:
            try:
                pygame.mixer.quit()
                pygame.mixer.init(sounddevice)
            except pygame.error:
                pygame.mixer.quit()
                pygame.mixer.init()


if __name__ == "__main__":
    pygame.init()
    set_sounddevice()
    pygame.mixer.music.load("c:/temp/test.flac")
    pygame.mixer.music.play()
    print("Playing music...")
    while pygame.mixer.music.get_busy():
        time.sleep(1)
    print("Music ended!")
