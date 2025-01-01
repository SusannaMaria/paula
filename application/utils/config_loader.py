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

import json
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"


def load_config():
    try:
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
            return config
    except FileNotFoundError:
        logger.error(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding '{CONFIG_FILE}': {e}")
        raise


def update_weight_config(changed_weights):
    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)

    feature_names = list(config["features"].keys())

    for i, feature in enumerate(feature_names):
        config["features"][feature]["weight"] = changed_weights[i]

    # Step 3: Save the updated config back to the file
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)
