import matplotlib.pyplot as plt

# Plot figure
plt.plot([1, 2, 3, 4], [1, 4, 9, 16])  # Sample data for plotting
plt.show(block=False)  # Show plot in a non-blocking way

# Introduce a short delay for the plot to display
plt.pause(0.01)

# Set title from console input
title = input("Enter the title for the plot: ")  # Prompt user for title input
plt.title(title)  # Set the plot title

# Resume the program to exit the plot window
plt.pause(0.01)
