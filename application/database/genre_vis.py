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
