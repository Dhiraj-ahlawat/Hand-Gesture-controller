"""
scratch/generate_flowchart.py
Generates a clean, professional system architecture and workflow diagram
for the Hand Gesture Controller report using Matplotlib.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "mini_project_report" / "screenshots" / "architecture_flowchart.png"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
ax.set_facecolor("#0B1325")
fig.patch.set_facecolor("#0B1325")

# Define stages
stages = [
    ("Webcam Input", "OpenCV VideoCapture\nBuffer Size = 1\n30 FPS Stream", "#0284C7"),
    ("Pre-Processing", "BGR to RGB Matrix\nNormalization\nAspect Ratio Fit", "#0369A1"),
    ("Hand Detection", "MediaPipe ML Model\n21 3D Landmarks\nConfidence >= 0.6", "#0D9488"),
    ("Geometric Rules", "Euclidean Distance\nPalm Scale Ratio\n9 Semantic Gestures", "#059669"),
    ("Temporal Filter", "Sliding Window Voting\nConsistency Thresh\n5-Frame Grace Buffer", "#D97706"),
    ("Safety Gates", "Default Disabled\nEdge Triggering\nCooldown Debounce", "#DC2626"),
    ("Action Dispatch", "CoreGraphics Mouse\nAppleScript Media\nInstant Emergency Stop", "#7C3AED"),
    ("Analytics & DB", "Event Deduplication\nSession Metrics\nSQLite (history.db)", "#2563EB"),
]

n = len(stages)
box_w = 0.95
box_h = 1.6
y_pos = 1.2

for i, (title, desc, color) in enumerate(stages):
    x_pos = 0.5 + i * 1.18
    # Draw rounded rectangle
    rect = patches.FancyBboxPatch(
        (x_pos, y_pos), box_w, box_h,
        boxstyle="round,pad=0.08,rounding_size=0.12",
        linewidth=1.5,
        edgecolor="#38BDF8",
        facecolor="#162544",
    )
    ax.add_patch(rect)
    
    # Top banner inside box
    header_rect = patches.FancyBboxPatch(
        (x_pos, y_pos + box_h - 0.42), box_w, 0.42,
        boxstyle="round,pad=0.08,rounding_size=0.08",
        linewidth=0,
        facecolor=color,
    )
    ax.add_patch(header_rect)
    
    # Text
    ax.text(x_pos + box_w / 2, y_pos + box_h - 0.21, title,
            ha="center", va="center", color="#FFFFFF", fontsize=8.5, fontweight="bold")
    ax.text(x_pos + box_w / 2, y_pos + 0.55, desc,
            ha="center", va="center", color="#94A3B8", fontsize=6.8, linespacing=1.25)
    
    # Step number circle
    circle = patches.Circle((x_pos + box_w / 2, y_pos + box_h + 0.32), 0.16, facecolor=color, edgecolor="#FFFFFF", lw=1)
    ax.add_patch(circle)
    ax.text(x_pos + box_w / 2, y_pos + box_h + 0.32, str(i + 1),
            ha="center", va="center", color="#FFFFFF", fontsize=7.5, fontweight="bold")

    # Arrow connecting to next box
    if i < n - 1:
        ax.annotate(
            "",
            xy=(x_pos + box_w + 0.22, y_pos + box_h / 2),
            xytext=(x_pos + box_w + 0.02, y_pos + box_h / 2),
            arrowprops=dict(arrowstyle="->", color="#38BDF8", lw=2, mutation_scale=12)
        )

# Thread boundary note at bottom
thread_box = patches.FancyBboxPatch(
    (0.5, 0.2), 9.25, 0.55,
    boxstyle="round,pad=0.06,rounding_size=0.08",
    linewidth=1,
    edgecolor="#334155",
    facecolor="#111E38",
)
ax.add_patch(thread_box)
ax.text(5.12, 0.47,
        "THREAD ARCHITECTURE: Background Capture Daemon Thread (Steps 1–5)  ⇄  Thread-Safe Locks  ⇄  Tkinter Main UI Thread (Steps 6–8)",
        ha="center", va="center", color="#38BDF8", fontsize=7.5, fontweight="bold")

ax.set_xlim(0.1, 10.2)
ax.set_ylim(0.0, 3.6)
ax.axis("off")
plt.tight_layout()
plt.savefig(str(OUTPUT_PATH), facecolor=fig.get_facecolor(), edgecolor="none", dpi=300)
plt.close()
print(f"Flowchart generated successfully at: {OUTPUT_PATH}")
