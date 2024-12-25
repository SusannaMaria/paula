import sqlite3
import matplotlib.pyplot as plt

# Connect to the database
database_path = "../database/paula.sqlite"
connection = sqlite3.connect(database_path)
cursor = connection.cursor()
# Features to analyze
features = ["danceability", "mood_sad", "mood_party"]

# Number of intervals
interval_count = 40
interval_size = 1 / interval_count

# Dictionary to store results for each feature
feature_distributions = {}

for feature in features:
    results = []
    for i in range(interval_count):
        lower_bound = i * interval_size
        upper_bound = lower_bound + interval_size

        # Query to count tracks in the current range for the current feature
        query = f"""
        SELECT COUNT(*)
        FROM track_features
        WHERE {feature} >= ? AND {feature} < ?;
        """
        cursor.execute(query, (lower_bound, upper_bound))
        count = cursor.fetchone()[0]
        results.append(count)

    # Store the results for the current feature
    feature_distributions[feature] = results

table_name = "track_features"

# Execute PRAGMA to get table info
cursor.execute(f"PRAGMA table_info({table_name});")
columns = cursor.fetchall()

# Extract column names
field_names = [
    column[1] for column in columns
]  # The second field contains the column name

# Print the field names
print(field_names)

# Close the connection
connection.close()

# Plot all graphs on one page
fig, axes = plt.subplots(len(features), 1, figsize=(10, 5 * len(features)))

for ax, feature in zip(axes, features):
    x_labels = [round(i * interval_size, 2) for i in range(interval_count)]
    ax.bar(x_labels, feature_distributions[feature], width=interval_size, align="edge")
    ax.set_title(f"Track Counts for {feature.capitalize()} Intervals")
    ax.set_xlabel(f"{feature.capitalize()} Range")
    ax.set_ylabel("Number of Tracks")

# Adjust layout to prevent overlap
plt.tight_layout()

# Show all graphs on one page
plt.show()
