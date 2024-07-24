import os
import glob
import argparse

f = []

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from plotnine import *
def prep_data(file_paths):
    # Read in data
    data_frames = []
    for f in file_paths:
        print(f"reading data from file: {f}")
        df = pd.read_csv(f, sep=",")
        df["preempt_interval_str"] = (df["preempt_interval"] / 1000).astype(int).astype(str) + "us"
 #       df["preempt_interval_str"] = pd.Categorical(df["preempt_interval_str"], categories=interval_order, ordered=True)
        df["config"] = df["preempt_type"] + " " + df["preempt_interval_str"]

 #       filtered_df = df[df["config"].str.contains("signal 10000us|signal 80us|signal 10us|uintr 10000us|uintr 50us|uintr 10us")]
 #       data_frames.append(filtered_df)
        # df = df[df['achieved']/df['target'] > 0.9]
        data_frames.append(df)

    all_data = pd.concat(data_frames, ignore_index=True)

    return all_data
def print_columns(data):
    print("Available columns for plotting:")
    for column in data.columns:
        print(f"- {column}")
def plot_latency_percentile_bimodal(all_data, percentile):
    # Plot settings
    plt.figure(figsize=(5.5, 4))

    # Short request type
    data_short = all_data[all_data['req_type'] == "short"]
    max_latency_short = data_short[percentile].max()
    
    # Plot short requests
    sns.lineplot(data=data_short, x="achieved", y=percentile, hue="config", style="preempt_type", markers=True, dashes=False)
    plt.xlabel("Achieved load (req/s)")
    plt.ylabel(f"{percentile} Latency (us)")
    plt.ylim(0, max_latency_short)
    plt.legend(title="Config and Preempt Type")
    plt.title(f"Latency for {percentile} Percentile (short)")
    plt.savefig(f"latency_{percentile}_short.pdf", dpi=300)
    plt.clf()

    # Long request type
    data_long = all_data[all_data['req_type'] == "long"]
    max_latency_long = data_long[percentile].max()
    
    # Plot long requests
    sns.lineplot(data=data_long, x="achieved", y=percentile, hue="config", style="preempt_type", markers=True, dashes=False)
    plt.xlabel("Achieved load (req/s)")
    plt.ylabel(f"{percentile} Latency (us)")
    plt.ylim(0, max_latency_long)
    plt.legend(title="Config and Preempt Type")
    plt.title(f"Latency for {percentile} Percentile (long)")
    plt.savefig(f"latency_{percentile}_long.pdf", dpi=300)
    plt.clf()

max_latency_short = {
    "p50": 1000,
    "p99": 2000,
    "p99.9": 5000
}

max_latency_long = {
    "p50": 2000,
    "p99": 10000,
    "p99.9": 10000
}

def theme_defaults():
    return theme_bw() + theme(legend_position=(0.3, 0.7), legend_direction='vertical',
        legend_key_size=10, legend_spacing=10, legend_title=element_blank())

def create_and_save_plot(data, req_type, percentile):
    plot = ggplot(data, aes(x="achieved", y=percentile, color="config", linetype="preempt_type")) + \
           geom_point() + \
           geom_line() + \
           theme_defaults() + \
           labs(x="Achieved load (req/s)", y=f"{percentile} Latency (us)") + \
           coord_cartesian(ylim=(0, max_latency_long[percentile] if req_type == "long" else max_latency_short[percentile]))
    plot.show()
    ggsave(plot, filename=f"latency_{percentile}_{req_type}.pdf", width=5.5, height=4, dpi=300)

# def plot_latency_percentile_bimodal(all_data, percentile):
#     data_short = all_data[all_data['req_type'] == "short"]

#     plot = ggplot(data_short, aes(x="achieved", y=percentile, color="config", linetype="preempt_type"))
#     plot = plot + geom_point() + geom_line()

#     plot = plot + theme_defaults()
#     plot = plot + labs(x="Achieved load (req/s)", y=f"{percentile} Latency (us)")
#     # plot = plot + ylim(0, min(data_short[percentile])*100)
#     plot = plot + coord_cartesian(ylim=(0, min(data_short[percentile])*100))
#     # plot = plot + coord_cartesian(ylim=(0, max_latency_short[percentile]))

#     plot.show()
#     ggsave(plot, filename=f"latency_{percentile}_short.pdf", width=5.5, height=4, dpi=300)

#     data_long = all_data[all_data['req_type'] == "long"]

#     plot = ggplot(data_long, aes(x="achieved", y=percentile, color="config", linetype="preempt_type"))
#     plot = plot + geom_point() + geom_line()

#     plot = plot + theme_defaults()
#     plot = plot + labs(x="Achieved load (req/s)", y=f"{percentile} Latency (us)")
#     plot = plot + coord_cartesian(ylim=(0, min(data_long[percentile])*100))
#     # plot = plot + coord_cartesian(ylim=(0, max_latency_long[percentile]))

#     plot.show()
#     ggsave(plot, filename=f"latency_{percentile}_long.pdf", width=5.5, height=4, dpi=300)

def plot_latency_percentile_bimodal(all_data, percentile):
    data_short = all_data[all_data['req_type'] == "short"]
    create_and_save_plot(data_short, "short", percentile)

    data_long = all_data[all_data['req_type'] == "long"]
    create_and_save_plot(data_long, "long", percentile)

    
def find_csv_files(directory):
    # Using glob.glob to find all CSV files recursively
    csv_files = glob.glob(os.path.join(directory, '**', '*.csv'), recursive=True)
    return csv_files  # This is a list of CSV file paths

def main():
    parser = argparse.ArgumentParser(description='Find all CSV files recursively from a given directory.')
    parser.add_argument('directory', type=str, help='The directory to search for CSV files.')
    args = parser.parse_args()
    
    global f
    f = find_csv_files(args.directory)
    print(f)

    all_data = prep_data(f)

    print_columns(all_data)
    plot_latency_percentile_bimodal(all_data, "p50")
    plot_latency_percentile_bimodal(all_data, "p99")
    plot_latency_percentile_bimodal(all_data, "p99.9")

if __name__ == '__main__':
    main()