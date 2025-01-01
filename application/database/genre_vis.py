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

import networkx as nx
from pyvis.network import Network

# Load the JSON data
file_path = "updated_genre_tree.json"
with open(file_path, "r") as f:
    genre_tree = json.load(f)

# Create a directed graph
G = nx.DiGraph()

# Add nodes and edges to the graph
for category, genres in genre_tree.items():
    if category == "uncategorized":
        category = "Uncategorized"  # Label for uncategorized group
    G.add_node(category, label=category, color="blue", shape="box")

    for genre_entry in genres:
        genre = genre_entry["genre"]
        count = genre_entry["count"]
        G.add_node(genre, label=f"{genre} ({count})", color="green")
        G.add_edge(category, genre)

# Create a Pyvis network for visualization
net = Network(notebook=True, directed=True)
net.from_nx(G)

# Set visualization options
net.show_buttons(filter_=["physics"])
output_html = "genre_tree_graph.html"
net.show(output_html)

output_html
