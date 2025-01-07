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

            exists = False
            for key, value in list_devices:
                if value == device["name"]:
                    exists = True
                    break
            if not exists:
                list_devices.append((idx, device["name"]))
        except pygame.error:
            pass
    return list_devices


def set_sounddevice(sounddevice=None):
    if not sounddevice:
        config = load_config()
        sounddevice = config.setdefault("sounddevice", "default")

    set_soundevice_by_name(sounddevice)


def set_soundevice_by_name(sounddevice):
    for key, value in get_sounddevices():
        if value == sounddevice:
            try:
                pygame.mixer.quit()
                pygame.mixer.init(key)
            except pygame.error:
                pygame.mixer.quit()
                pygame.mixer.init()
            finally:
                return
