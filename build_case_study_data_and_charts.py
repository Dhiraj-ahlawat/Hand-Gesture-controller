"""
build_case_study_data_and_charts.py
Generates the illustrative dataset, performs data cleaning, calculates NumPy/Pandas statistics,
and renders all 10 Matplotlib and Seaborn charts for the Hand Gesture Controller Case Study.
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Set deterministic random seeds for full academic reproducibility
np.random.seed(42)

OUTPUT_DIR = Path("case_study_output")
CHARTS_DIR = OUTPUT_DIR / "charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Dataset Generation (Illustrative Telemetry Dataset)
# ---------------------------------------------------------------------------
def generate_raw_dataset() -> pd.DataFrame:
    """Generate realistic illustrative gesture telemetry records across 25 sessions."""
    gestures_pool = [
        "Thumbs Up", "Peace Sign", "Open Palm", "Fist", "One Finger",
        "Two Fingers", "Three Fingers", "Four Fingers", "Five Fingers", "Unknown Gesture"
    ]
    # Realistic weights based on typical desktop user interaction
    gesture_weights = [0.22, 0.18, 0.15, 0.12, 0.08, 0.07, 0.05, 0.04, 0.04, 0.05]

    action_map = {
        "Thumbs Up": "Play/Pause",
        "Peace Sign": "Next Track",
        "Open Palm": "Mute",
        "Fist": "Continuous Volume",
        "One Finger": "Virtual Mouse Click",
        "Two Fingers": "Previous Track",
        "Three Fingers": "No Action Mapped",
        "Four Fingers": "No Action Mapped",
        "Five Fingers": "No Action Mapped",
        "Unknown Gesture": "No Action Mapped",
    }

    n_records = 850
    records = []
    
    # 25 unique sessions across multiple days
    session_ids = [f"sess_20261027_{1000 + i*15:04d}_{hex(100000 + i*337)[2:8]}" for i in range(25)]
    session_durations = {sess: float(np.random.uniform(45.0, 360.0)) for sess in session_ids}
    session_start_times = {
        sess: pd.Timestamp("2026-10-27 09:00:00") + pd.Timedelta(minutes=i * 25)
        for i, sess in enumerate(session_ids)
    }

    for i in range(n_records):
        evt_id = f"EVT_{i+1:04d}"
        sess_id = np.random.choice(session_ids)
        base_time = session_start_times[sess_id]
        dur = session_durations[sess_id]
        evt_time = base_time + pd.Timedelta(seconds=float(np.random.uniform(1.0, dur)))

        # Gesture selection
        g_name = np.random.choice(gestures_pool, p=gesture_weights)
        handedness = np.random.choice(["Right", "Left"], p=[0.74, 0.26])

        # Confidence score (Beta distribution skewed towards 0.85-0.95)
        conf = float(np.clip(np.random.beta(12, 2.5), 0.60, 0.99))

        # Latency in ms (Lognormal with peak ~16 ms on Apple M2)
        latency = float(np.random.lognormal(mean=2.75, sigma=0.18))

        mapped_act = action_map[g_name]

        # Action outcome
        if mapped_act == "No Action Mapped":
            outcome = "No Action Mapped"
        else:
            # 82% success, 14% blocked (safe mode), 4% failed (accessibility/system)
            outcome = np.random.choice(["Success", "Blocked", "Failed"], p=[0.82, 0.14, 0.04])

        fps = float(np.clip(np.random.normal(29.8, 0.6), 25.0, 31.0))

        records.append({
            "event_id": evt_id,
            "session_id": sess_id,
            "timestamp": evt_time.strftime("%Y-%m-%d %H:%M:%S"),
            "gesture_name": g_name,
            "handedness": handedness,
            "confidence_score": round(conf, 4),
            "latency_ms": round(latency, 2),
            "mapped_action": mapped_act,
            "action_outcome": outcome,
            "session_duration_sec": round(dur, 1),
            "fps": round(fps, 1),
        })

    df = pd.DataFrame(records)

    # Inject realistic data cleaning scenarios:
    # 1. Missing values
    nan_conf_idx = np.random.choice(n_records, size=8, replace=False)
    df.loc[nan_conf_idx, "confidence_score"] = np.nan

    nan_lat_idx = np.random.choice(n_records, size=10, replace=False)
    df.loc[nan_lat_idx, "latency_ms"] = np.nan

    active_indices = df[df["mapped_action"] != "No Action Mapped"].index
    nan_out_idx = np.random.choice(active_indices, size=12, replace=False)
    df.loc[nan_out_idx, "action_outcome"] = np.nan

    # 2. Inconsistent categorical spellings
    inconsistencies = [
        ("Thumbs Up", "thumbs_up", 7),
        ("Peace Sign", "peace", 5),
        ("Open Palm", "open_palm", 6),
    ]
    for orig, typo, count in inconsistencies:
        match_idx = df[df["gesture_name"] == orig].index[:count]
        df.loc[match_idx, "gesture_name"] = typo

    # 3. Invalid out-of-range values (anomalies)
    df.loc[15, "latency_ms"] = -14.5
    df.loc[42, "latency_ms"] = -22.0
    df.loc[88, "latency_ms"] = -8.1
    df.loc[105, "confidence_score"] = 1.78
    df.loc[210, "confidence_score"] = -0.15

    # 4. Exact duplicate rows (simulating duplicate transmission / sensor glitch)
    dup_rows = df.iloc[[10, 25, 45, 120, 180, 250]].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


# ---------------------------------------------------------------------------
# 2. Data Cleaning Pipeline
# ---------------------------------------------------------------------------
def clean_dataset(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Perform systematic data cleaning using Pandas and capture before/after metrics."""
    metrics = {}
    metrics["raw_shape"] = df_raw.shape
    metrics["raw_missing"] = df_raw.isnull().sum().to_dict()
    metrics["raw_duplicates"] = int(df_raw.duplicated().sum())

    # Step 1: Remove exact duplicate rows
    df_step1 = df_raw.drop_duplicates().copy()
    metrics["duplicates_removed"] = metrics["raw_duplicates"]

    # Step 2: Normalize inconsistent categorical strings
    label_fixes = {
        "thumbs_up": "Thumbs Up",
        "peace": "Peace Sign",
        "open_palm": "Open Palm",
    }
    metrics["inconsistent_labels_before"] = {k: int((df_step1["gesture_name"] == k).sum()) for k in label_fixes}
    df_step1["gesture_name"] = df_step1["gesture_name"].replace(label_fixes)
    metrics["inconsistent_labels_after"] = {k: int((df_step1["gesture_name"] == k).sum()) for k in label_fixes}

    # Step 3: Handle out-of-range numerical anomalies
    metrics["invalid_latency_before"] = int((df_step1["latency_ms"] < 0).sum())
    metrics["invalid_conf_before"] = int(((df_step1["confidence_score"] < 0) | (df_step1["confidence_score"] > 1.0)).sum())

    # Replace impossible values with NaN so they can be imputed systematically
    df_step1.loc[df_step1["latency_ms"] < 0, "latency_ms"] = np.nan
    df_step1.loc[(df_step1["confidence_score"] < 0) | (df_step1["confidence_score"] > 1.0), "confidence_score"] = np.nan

    # Step 4: Missing value imputation with justified statistical methods
    median_latency = float(df_step1["latency_ms"].median())
    median_conf = float(df_step1["confidence_score"].median())
    metrics["imputed_median_latency"] = round(median_latency, 2)
    metrics["imputed_median_confidence"] = round(median_conf, 4)

    df_step1["latency_ms"] = df_step1["latency_ms"].fillna(median_latency)
    df_step1["confidence_score"] = df_step1["confidence_score"].fillna(median_conf)

    # Impute missing action outcome with modal outcome ('Success') for mapped actions
    df_step1["action_outcome"] = df_step1["action_outcome"].fillna("Success")

    # Step 5: Convert types
    df_step1["timestamp"] = pd.to_datetime(df_step1["timestamp"])
    df_step1["event_hour"] = df_step1["timestamp"].dt.hour
    df_step1["confidence_score"] = df_step1["confidence_score"].astype(float)
    df_step1["latency_ms"] = df_step1["latency_ms"].astype(float)
    df_step1["session_duration_sec"] = df_step1["session_duration_sec"].astype(float)
    df_step1["fps"] = df_step1["fps"].astype(float)

    metrics["clean_shape"] = df_step1.shape
    metrics["clean_missing"] = df_step1.isnull().sum().to_dict()

    return df_step1, metrics


# ---------------------------------------------------------------------------
# 3. Statistical Analysis Using NumPy & Pandas
# ---------------------------------------------------------------------------
def compute_statistics(df: pd.DataFrame) -> dict:
    """Calculate descriptive, grouping, and correlation statistics."""
    stats = {}

    # Numerical columns summary
    num_cols = ["confidence_score", "latency_ms", "session_duration_sec", "fps"]
    for col in num_cols:
        arr = df[col].to_numpy()
        stats[col] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=1)),
            "median": float(np.median(arr)),
            "q25": float(np.percentile(arr, 25)),
            "q75": float(np.percentile(arr, 75)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }

    # Gesture frequency & percentage
    gesture_counts = df["gesture_name"].value_counts()
    gesture_pcts = (df["gesture_name"].value_counts(normalize=True) * 100).round(2)
    stats["gesture_distribution"] = pd.DataFrame({
        "Count": gesture_counts,
        "Percentage (%)": gesture_pcts
    }).to_dict(orient="index")

    # Action outcome summary
    action_counts = df["action_outcome"].value_counts()
    action_pcts = (df["action_outcome"].value_counts(normalize=True) * 100).round(2)
    stats["action_outcomes"] = pd.DataFrame({
        "Count": action_counts,
        "Percentage (%)": action_pcts
    }).to_dict(orient="index")

    # Groupby gesture: Mean Confidence & Latency
    grouped_g = df.groupby("gesture_name").agg({
        "confidence_score": ["mean", "median", "std"],
        "latency_ms": ["mean", "median", "std"],
        "event_id": "count"
    })
    grouped_g.columns = [f"{col[0]}_{col[1]}" for col in grouped_g.columns]
    stats["grouped_gestures"] = grouped_g.round(3).to_dict(orient="index")

    # Correlation Matrix
    corr_matrix = df[num_cols].corr().round(4)
    stats["correlation_matrix"] = corr_matrix.to_dict()

    # Session level summary
    sess_summary = df.groupby("session_id").agg({
        "event_id": "count",
        "session_duration_sec": "first",
        "latency_ms": "mean",
        "confidence_score": "mean"
    }).rename(columns={"event_id": "total_events"})
    stats["session_summary"] = {
        "mean_events_per_session": float(sess_summary["total_events"].mean()),
        "median_events_per_session": float(sess_summary["total_events"].median()),
        "std_events_per_session": float(sess_summary["total_events"].std()),
        "mean_duration": float(sess_summary["session_duration_sec"].mean()),
        "min_duration": float(sess_summary["session_duration_sec"].min()),
        "max_duration": float(sess_summary["session_duration_sec"].max()),
    }

    return stats


# ---------------------------------------------------------------------------
# 4. Data Visualization (Matplotlib & Seaborn)
# ---------------------------------------------------------------------------
def generate_visualizations(df: pd.DataFrame):
    """Render and save all 10 Matplotlib and Seaborn charts."""
    # Styling configuration
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    palette = sns.color_palette("mako")

    # =======================================================================
    # MATPLOTLIB CHART 1: Line Chart (Gesture Events Timeline)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)
    df_sorted["cumulative_events"] = np.arange(1, len(df_sorted) + 1)
    
    # Resample to 30-minute intervals
    df_timeline = df.set_index("timestamp").resample("30min")["event_id"].count()
    
    ax.plot(df_timeline.index, df_timeline.values, marker="o", color="#1F4E79", linewidth=2.2, markersize=6, label="Events per 30-min window")
    ax.set_title("Timeline of Gesture Interaction Events Across Sessions", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Session Timestamp (Hour:Minute)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Recognized Event Frequency", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.6)
    plt.xticks(rotation=25)
    ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#CBD5E1")
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig1_matplotlib_line_chart.png")
    plt.close(fig)

    # =======================================================================
    # MATPLOTLIB CHART 2: Bar Chart (Gesture Frequency Distribution)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    g_counts = df["gesture_name"].value_counts()
    colors = plt.cm.Blues(np.linspace(0.85, 0.40, len(g_counts)))

    bars = ax.bar(g_counts.index, g_counts.values, color=colors, edgecolor="#0F172A", linewidth=1.0, width=0.65)
    ax.set_title("Recognized Hand Gesture Frequency Distribution", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Gesture Category", fontsize=11, fontweight="bold")
    ax.set_ylabel("Total Event Count", fontsize=11, fontweight="bold")
    ax.set_ylim(0, max(g_counts.values) * 1.15)
    plt.xticks(rotation=30, ha="right", fontsize=10)

    # Value labels on top of bars
    for bar in bars:
        h = bar.get_height()
        pct = (h / len(df)) * 100
        ax.annotate(f"{h}\n({pct:.1f}%)", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig2_matplotlib_bar_chart.png")
    plt.close(fig)

    # =======================================================================
    # MATPLOTLIB CHART 3: Histogram (Latency Distribution)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    latencies = df["latency_ms"]
    mean_lat = float(np.mean(latencies))
    median_lat = float(np.median(latencies))

    n, bins, patches = ax.hist(latencies, bins=25, color="#2E75B6", edgecolor="#1F4E79", alpha=0.85, density=False)
    ax.axvline(mean_lat, color="#DC2626", linestyle="--", linewidth=2.0, label=f"Mean Latency ({mean_lat:.2f} ms)")
    ax.axvline(median_lat, color="#10B981", linestyle="-.", linewidth=2.0, label=f"Median Latency ({median_lat:.2f} ms)")

    ax.set_title("Distribution of Gesture Recognition Latency (Inference & Tracking)", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Processing Latency (Milliseconds)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Frequency (Frames)", fontsize=11, fontweight="bold")
    ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#CBD5E1", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig3_matplotlib_histogram.png")
    plt.close(fig)

    # =======================================================================
    # MATPLOTLIB CHART 4: Pie Chart (Action Outcomes)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
    outcomes = df["action_outcome"].value_counts()
    pie_colors = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444"]
    explode = (0.05, 0.0, 0.0, 0.0) if len(outcomes) >= 4 else None

    wedges, texts, autotexts = ax.pie(
        outcomes.values,
        labels=outcomes.index,
        autopct="%1.1f%%",
        startangle=140,
        colors=pie_colors[:len(outcomes)],
        explode=explode[:len(outcomes)] if explode else None,
        shadow=True,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5}
    )
    plt.setp(autotexts, size=10, weight="bold", color="white")
    plt.setp(texts, size=11, weight="bold")
    ax.set_title("System Action Outcome Proportions Across All Sessions", fontsize=14, fontweight="bold", pad=14, color="#1F4E79")
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig4_matplotlib_pie_chart.png")
    plt.close(fig)

    # =======================================================================
    # MATPLOTLIB CHART 5: Scatter Plot (Confidence vs. Latency)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    ax.scatter(df["confidence_score"], df["latency_ms"], c=df["latency_ms"], cmap="viridis", alpha=0.65, edgecolors="none", s=40)
    
    # Add polynomial trendline (linear)
    m, b = np.polyfit(df["confidence_score"], df["latency_ms"], 1)
    x_line = np.linspace(df["confidence_score"].min(), df["confidence_score"].max(), 100)
    ax.plot(x_line, m * x_line + b, color="#DC2626", linewidth=2.0, linestyle="--", label=f"Trendline (slope = {m:.2f})")

    ax.set_title("Landmark Detection Confidence vs. Processing Latency", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Perception Confidence Score (0.0 to 1.0)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Inference & Processing Latency (ms)", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#CBD5E1")
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig5_matplotlib_scatter_plot.png")
    plt.close(fig)

    # =======================================================================
    # SEABORN CHART 6: Box Plot (Latency Grouped by Gesture)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    order = df.groupby("gesture_name")["latency_ms"].median().sort_values(ascending=False).index
    sns.boxplot(
        data=df,
        x="gesture_name",
        y="latency_ms",
        order=order,
        palette="crest",
        ax=ax,
        linewidth=1.3,
        fliersize=3.5,
    )
    ax.set_title("Processing Latency Dispersion Grouped by Gesture Type (Box Plot)", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Gesture Category", fontsize=11, fontweight="bold")
    ax.set_ylabel("Latency (Milliseconds)", fontsize=11, fontweight="bold")
    plt.xticks(rotation=30, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig6_seaborn_box_plot.png")
    plt.close(fig)

    # =======================================================================
    # SEABORN CHART 7: Violin Plot (Confidence Score Across Top Gestures)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    top_gestures = df["gesture_name"].value_counts().head(6).index
    df_top = df[df["gesture_name"].isin(top_gestures)]

    sns.violinplot(
        data=df_top,
        x="gesture_name",
        y="confidence_score",
        palette="Blues_r",
        inner="quartile",
        ax=ax,
        cut=0,
    )
    ax.set_title("Detection Confidence Density Across Top 6 Gestures (Violin Plot)", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Top Gesture Categories", fontsize=11, fontweight="bold")
    ax.set_ylabel("Confidence Score Distribution", fontsize=11, fontweight="bold")
    plt.xticks(rotation=20, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig7_seaborn_violin_plot.png")
    plt.close(fig)

    # =======================================================================
    # SEABORN CHART 8: Heatmap (Correlation Matrix)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(8, 6.5), dpi=300)
    num_cols = ["confidence_score", "latency_ms", "session_duration_sec", "fps"]
    corr = df[num_cols].corr()

    rename_labels = {
        "confidence_score": "Confidence",
        "latency_ms": "Latency (ms)",
        "session_duration_sec": "Duration (s)",
        "fps": "Camera FPS"
    }
    corr_renamed = corr.rename(index=rename_labels, columns=rename_labels)

    sns.heatmap(
        corr_renamed,
        annot=True,
        fmt=".3f",
        cmap="coolwarm",
        vmin=-0.25,
        vmax=0.25,
        linewidths=1.2,
        cbar_kws={"label": "Pearson Correlation Coefficient (r)"},
        ax=ax,
        annot_kws={"size": 11, "weight": "bold"}
    )
    ax.set_title("Correlation Matrix of Numeric Telemetry Variables", fontsize=14, fontweight="bold", pad=14, color="#1F4E79")
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig8_seaborn_heatmap.png")
    plt.close(fig)

    # =======================================================================
    # SEABORN CHART 9: Count Plot (Mapped Action by Handedness)
    # =======================================================================
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    action_order = df["mapped_action"].value_counts().index
    sns.countplot(
        data=df,
        x="mapped_action",
        hue="handedness",
        order=action_order,
        palette=["#2563EB", "#F97316"],
        ax=ax,
        edgecolor="#1E293B"
    )
    ax.set_title("Frequency of Mapped System Actions Disaggregated by Handedness", fontsize=14, fontweight="bold", pad=12, color="#1F4E79")
    ax.set_xlabel("Mapped System Action", fontsize=11, fontweight="bold")
    ax.set_ylabel("Action Trigger Count", fontsize=11, fontweight="bold")
    plt.xticks(rotation=25, ha="right")
    ax.legend(title="Detected Hand", frameon=True, facecolor="#F8FAFC", edgecolor="#CBD5E1")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "fig9_seaborn_count_plot.png")
    plt.close(fig)

    # =======================================================================
    # SEABORN CHART 10: Pair Plot (Multivariate Numeric Grid)
    # =======================================================================
    # Filter out 'None' outcomes for clean visual clustering
    df_pair = df[df["action_outcome"].isin(["Success", "Blocked", "Failed"])].copy()
    pair_grid = sns.pairplot(
        df_pair,
        vars=["confidence_score", "latency_ms", "session_duration_sec"],
        hue="action_outcome",
        palette={"Success": "#10B981", "Blocked": "#3B82F6", "Failed": "#EF4444"},
        diag_kind="kde",
        plot_kws={"alpha": 0.6, "s": 30},
        diag_kws={"fill": True},
        height=2.5,
        aspect=1.2
    )
    pair_grid.fig.subplots_adjust(top=0.92)
    pair_grid.fig.suptitle("Multivariate Pair Plot of Perception, Latency, and Session Metrics", fontsize=13, fontweight="bold", color="#1F4E79")
    pair_grid.savefig(CHARTS_DIR / "fig10_seaborn_pair_plot.png", dpi=300)
    plt.close(pair_grid.fig)


# ---------------------------------------------------------------------------
# Main Execution Pipeline
# ---------------------------------------------------------------------------
def main():
    print("[1/4] Generating raw illustrative dataset...")
    df_raw = generate_raw_dataset()
    raw_path = OUTPUT_DIR / "case_study_dataset.csv"
    df_raw.to_csv(raw_path, index=False)
    print(f"      Saved raw dataset ({len(df_raw)} records) to {raw_path}")

    print("[2/4] Executing Pandas data cleaning pipeline...")
    df_clean, clean_metrics = clean_dataset(df_raw)
    clean_path = OUTPUT_DIR / "case_study_cleaned.csv"
    df_clean.to_csv(clean_path, index=False)
    print(f"      Cleaned dataset ({len(df_clean)} records) saved to {clean_path}")

    print("[3/4] Computing NumPy & Pandas statistical metrics...")
    stats = compute_statistics(df_clean)
    with open(OUTPUT_DIR / "case_study_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    with open(OUTPUT_DIR / "cleaning_metrics.json", "w") as f:
        json.dump(clean_metrics, f, indent=2)
    print("      Statistical metrics saved to case_study_stats.json")

    print("[4/4] Rendering 10 Matplotlib & Seaborn high-resolution visualizations...")
    generate_visualizations(df_clean)
    print(f"      All 10 charts saved successfully into {CHARTS_DIR}")
    print("\nData and visual generation complete!")

if __name__ == "__main__":
    main()
