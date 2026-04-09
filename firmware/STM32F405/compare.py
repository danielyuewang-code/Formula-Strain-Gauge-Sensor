"""
visualizer.py

Strain Gauge Data Visualization
Formula Racing SAE — UBC

Plots processed suspension load data from the pipeline:
1. All 4 channels force vs time
2. Raw vs filtered comparison (to show filter effect)
3. Synchronized strain gauge + accelerometer overlay
4. Per-channel summary statistics bar chart

Usage:
    from pipeline import DataProcessor
    from visualizer import DataVisualizer

    processor = DataProcessor("data/run_001.csv").run()
    viz = DataVisualizer(processor)
    viz.plot_all_channels()
    viz.plot_raw_vs_filtered()
    viz.plot_synchronized()
    viz.plot_summary()
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

CHANNEL_NAMES  = ["Front Left", "Front Right", "Rear Left", "Rear Right"]
CHANNEL_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]  # standard matplotlib colors


class DataVisualizer:
    """
    Visualizes processed strain gauge data using matplotlib.

    Takes a completed DataProcessor object and generates plots.
    Each method produces one standalone figure.
    """

    def __init__(self, processor):
        """
        Parameters
        ----------
        processor : DataProcessor
            A DataProcessor instance that has already had .run() called
        """
        self.processor = processor
        self.time      = processor.timestamps
        self.raw       = processor.force_raw
        self.filtered  = processor.force_filtered

    # ─────────────────────────────────────────────────────────
    # PLOT 1 — ALL 4 CHANNELS, FILTERED FORCE VS TIME
    # Shows suspension load on each wheel over the run
    # ─────────────────────────────────────────────────────────

    def plot_all_channels(self, save_path=None):
        """
        Plot filtered force vs time for all 4 channels as stacked subplots.

        Each channel gets its own subplot so they're easy to read
        without overlapping — especially useful when loads differ
        significantly between front and rear.
        """
        fig, axes = plt.subplots(
            nrows=4,
            ncols=1,
            figsize=(14, 10),
            sharex=True    # all subplots share the same x axis (time)
        )

        fig.suptitle("Suspension Load — All Channels", fontsize=14, fontweight='bold')

        for ch in range(4):
            axes[ch].plot(
                self.time,
                self.filtered[:, ch],
                color=CHANNEL_COLORS[ch],
                linewidth=0.8,
                label=CHANNEL_NAMES[ch]
            )

            axes[ch].set_ylabel("Force (N)")
            axes[ch].set_title(CHANNEL_NAMES[ch], fontsize=10)
            axes[ch].grid(True, alpha=0.3)

            # Mark zero load line for reference
            axes[ch].axhline(y=0, color='black', linewidth=0.5, linestyle='--', alpha=0.5)

        # Only bottom subplot needs x label (shared axis)
        axes[-1].set_xlabel("Time (s)")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved to {save_path}")

        plt.show()

    # ─────────────────────────────────────────────────────────
    # PLOT 2 — RAW VS FILTERED COMPARISON
    # Shows the effect of the moving average filter
    # Useful for validating filter is working correctly
    # ─────────────────────────────────────────────────────────

    def plot_raw_vs_filtered(self, channel=0, save_path=None):
        """
        Overlay raw and filtered data for one channel.

        Shows clearly how much noise the moving average filter removed.
        Default channel 0 = Front Left.

        Parameters
        ----------
        channel : int — which channel to plot (0=FL, 1=FR, 2=RL, 3=RR)
        """
        fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(14, 7), sharex=True)

        fig.suptitle(
            f"Raw vs Filtered — {CHANNEL_NAMES[channel]}",
            fontsize=14, fontweight='bold'
        )

        # Top plot — raw data
        axes[0].plot(
            self.time,
            self.raw[:, channel],
            color='gray',
            linewidth=0.6,
            alpha=0.8,
            label='Raw'
        )
        axes[0].set_ylabel("Force (N)")
        axes[0].set_title("Raw (unfiltered)", fontsize=10)
        axes[0].grid(True, alpha=0.3)
        axes[0].legend()

        # Bottom plot — filtered data
        axes[1].plot(
            self.time,
            self.filtered[:, channel],
            color=CHANNEL_COLORS[channel],
            linewidth=0.8,
            label='Filtered'
        )
        axes[1].set_ylabel("Force (N)")
        axes[1].set_xlabel("Time (s)")
        axes[1].set_title("Filtered (moving average)", fontsize=10)
        axes[1].grid(True, alpha=0.3)
        axes[1].legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved to {save_path}")

        plt.show()

    # ─────────────────────────────────────────────────────────
    # PLOT 3 — SYNCHRONIZED STRAIN GAUGE + ACCELEROMETER
    # Overlays suspension load with accelerometer data
    # Lets you see correlation — when the car corners hard,
    # does the suspension load match the g-force?
    # ─────────────────────────────────────────────────────────

    def plot_synchronized(self, accelerometer_data, accel_timestamps, save_path=None):
        """
        Overlay suspension load with accelerometer data on shared time axis.

        Synchronization lets you correlate suspension events with
        vehicle dynamics — e.g. high lateral g → higher outer wheel load.

        Parameters
        ----------
        accelerometer_data  : np.ndarray shape (M,) — accelerometer readings (g)
        accel_timestamps    : np.ndarray shape (M,) — accelerometer timestamps (s)
        """
        fig = plt.figure(figsize=(14, 8))

        # Use gridspec for flexible subplot sizing
        # Give suspension plots more height than accelerometer
        gs = gridspec.GridSpec(3, 1, height_ratios=[2, 2, 1])

        ax_front = fig.add_subplot(gs[0])
        ax_rear  = fig.add_subplot(gs[1], sharex=ax_front)
        ax_accel = fig.add_subplot(gs[2], sharex=ax_front)

        fig.suptitle("Suspension Load vs Accelerometer — Synchronized", 
                     fontsize=14, fontweight='bold')

        # Front axle — FL and FR on same plot
        ax_front.plot(self.time, self.filtered[:, 0],
                      color=CHANNEL_COLORS[0], linewidth=0.8, label='Front Left')
        ax_front.plot(self.time, self.filtered[:, 1],
                      color=CHANNEL_COLORS[1], linewidth=0.8, label='Front Right')
        ax_front.set_ylabel("Force (N)")
        ax_front.set_title("Front Axle", fontsize=10)
        ax_front.legend(loc='upper right', fontsize=8)
        ax_front.grid(True, alpha=0.3)
        ax_front.axhline(y=0, color='black', linewidth=0.5, linestyle='--', alpha=0.5)

        # Rear axle — RL and RR on same plot
        ax_rear.plot(self.time, self.filtered[:, 2],
                     color=CHANNEL_COLORS[2], linewidth=0.8, label='Rear Left')
        ax_rear.plot(self.time, self.filtered[:, 3],
                     color=CHANNEL_COLORS[3], linewidth=0.8, label='Rear Right')
        ax_rear.set_ylabel("Force (N)")
        ax_rear.set_title("Rear Axle", fontsize=10)
        ax_rear.legend(loc='upper right', fontsize=8)
        ax_rear.grid(True, alpha=0.3)
        ax_rear.axhline(y=0, color='black', linewidth=0.5, linestyle='--', alpha=0.5)

        # Accelerometer — lateral g-force
        ax_accel.plot(accel_timestamps, accelerometer_data,
                      color='purple', linewidth=0.8, label='Lateral G')
        ax_accel.set_ylabel("G-Force (g)")
        ax_accel.set_xlabel("Time (s)")
        ax_accel.set_title("Accelerometer", fontsize=10)
        ax_accel.legend(loc='upper right', fontsize=8)
        ax_accel.grid(True, alpha=0.3)
        ax_accel.axhline(y=0, color='black', linewidth=0.5, linestyle='--', alpha=0.5)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved to {save_path}")

        plt.show()

    # ─────────────────────────────────────────────────────────
    # PLOT 4 — SUMMARY STATISTICS BAR CHART
    # Shows mean, max, min force per channel
    # Quick way to compare suspension loading across wheels
    # Useful for checking if suspension setup is balanced
    # ─────────────────────────────────────────────────────────

    def plot_summary(self, save_path=None):
        """
        Bar chart of mean, max, and min force per channel.

        Gives a quick overview of how loaded each wheel was
        across the whole run — useful for comparing suspension setups.
        """
        means = np.mean(self.filtered, axis=0)    # mean per channel
        maxes = np.max(self.filtered, axis=0)     # max per channel
        mins  = np.min(self.filtered, axis=0)     # min per channel

        x = np.arange(4)         # 4 channel positions
        width = 0.25              # width of each bar group

        fig, ax = plt.subplots(figsize=(10, 6))

        # Three groups of bars — mean, max, min
        bars_mean = ax.bar(x - width, means, width, label='Mean', color='steelblue', alpha=0.8)
        bars_max  = ax.bar(x,         maxes, width, label='Max',  color='tomato',    alpha=0.8)
        bars_min  = ax.bar(x + width, mins,  width, label='Min',  color='seagreen',  alpha=0.8)

        # Labels and formatting
        ax.set_xlabel("Channel")
        ax.set_ylabel("Force (N)")
        ax.set_title("Suspension Load Summary — Per Channel", fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(CHANNEL_NAMES)
        ax.legend()
        ax.grid(True, axis='y', alpha=0.3)
        ax.axhline(y=0, color='black', linewidth=0.8)

        # Add value labels on top of each bar
        for bar in [*bars_mean, *bars_max, *bars_min]:
            height = bar.get_height()
            ax.annotate(
                f'{height:.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom', fontsize=8
            )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved to {save_path}")

        plt.show()


# ─────────────────────────────────────────────────────────
# ENTRY POINT — run with synthetic data for testing
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Demo with synthetic data since car is not ready yet.
    Generates realistic looking suspension load data to
    validate the visualizer works correctly.
    """

    # Generate synthetic time axis — 10 second run at 100Hz
    num_samples = 1000
    time = np.linspace(0, 10, num_samples)

    # Synthetic suspension data — sine waves with noise
    # Simulates oscillating suspension loads during a run
    np.random.seed(42)

    raw_force = np.column_stack([
        500 + 200 * np.sin(2 * np.pi * 1.5 * time) + 30 * np.random.randn(num_samples),
        480 + 180 * np.sin(2 * np.pi * 1.5 * time + 0.3) + 30 * np.random.randn(num_samples),
        420 + 150 * np.sin(2 * np.pi * 1.2 * time) + 25 * np.random.randn(num_samples),
        410 + 160 * np.sin(2 * np.pi * 1.2 * time + 0.2) + 25 * np.random.randn(num_samples),
    ])

    # Apply moving average filter manually for demo
    from pipeline import DataFilter
    filtered_force = DataFilter(window_size=10).apply(raw_force)

    # Synthetic accelerometer — lateral g-force
    accel = 2.0 * np.sin(2 * np.pi * 0.8 * time) + 0.2 * np.random.randn(num_samples)

    # Build a minimal mock processor object so DataVisualizer works
    class MockProcessor:
        def __init__(self):
            self.timestamps    = time
            self.force_raw     = raw_force
            self.force_filtered = filtered_force

    viz = DataVisualizer(MockProcessor())

    # Generate all plots
    viz.plot_all_channels()
    viz.plot_raw_vs_filtered(channel=0)
    viz.plot_synchronized(accel, time)
    viz.plot_summary()
