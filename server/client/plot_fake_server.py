from plotnine import *
import pandas as pd
import re
import sys

def print_columns(data):
    print("Available columns for plotting:")
    for column in data.columns:
        print(f"- {column}")

def theme_defaults():
    return theme_bw() + theme(legend_position=(0.3, 0.7), legend_direction='vertical',
        legend_key_size=10, legend_spacing=10, legend_title=element_blank())

def print_entire_df(data):
    print(data.to_string(index=False))

interval_order = ["10000us", "500us", "100us", "50us", "10us"]

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
        data_frames.append(df)

    all_data = pd.concat(data_frames, ignore_index=True)

    return all_data

max_latency = {
    "p50": 1000,
    "p99": 5000,
    "p99.9": 5000
}

def plot_latency_percentile(all_data, percentile):
    plot = ggplot(all_data, aes(x="achieved", y=percentile, color="config", linetype="preempt_type"))
    plot = plot + geom_point() + geom_line()

    plot = plot + theme_defaults()
    plot = plot + labs(x="Achieved load (req/s)", y=f"{percentile} Latency (us)")
    plot = plot + coord_cartesian(ylim=(0,max_latency[percentile]))

    ggsave(plot, filename=f"latency_{percentile}.pdf", width=5.5, height=4, dpi=300)


max_latency_short = {
    "p50": 1000,
    "p99": 5000,
    "p99.9": 5000
}

max_latency_long = {
    "p50": 2000,
    "p99": 10000,
    "p99.9": 10000
}

def plot_latency_percentile_bimodal(all_data, percentile):
    data_short = all_data[all_data['req_type'] == "1us"]

    plot = ggplot(data_short, aes(x="achieved", y=percentile, color="config", linetype="preempt_type"))
    plot = plot + geom_point() + geom_line()

    plot = plot + theme_defaults()
    plot = plot + labs(x="Achieved load (req/s)", y=f"{percentile} Latency (us)")
    plot = plot + coord_cartesian(ylim=(0, max_latency_short[percentile]))

    ggsave(plot, filename=f"latency_{percentile}_short.pdf", width=5.5, height=4, dpi=300)

    data_long = all_data[all_data['req_type'] == "260us"]

    plot = ggplot(data_long, aes(x="achieved", y=percentile, color="config", linetype="preempt_type"))
    plot = plot + geom_point() + geom_line()

    plot = plot + theme_defaults()
    plot = plot + labs(x="Achieved load (req/s)", y=f"{percentile} Latency (us)")
    plot = plot + coord_cartesian(ylim=(0, max_latency_long[percentile]))

    ggsave(plot, filename=f"latency_{percentile}_long.pdf", width=5.5, height=4, dpi=300)

def plot_preemption_overhead(summary_data):
    max_tput = summary_data['achieved'].max()

    # need to adjust for the number of cores
    summary_data['observed_interval_us'] = summary_data['duration'] * 1000 * 1000 / summary_data['preemptgen']

    # plot max throughput
    plot = ggplot(summary_data, aes(x="observed_interval_us", y="achieved",
        color="preempt_type", linetype="preempt_type"))
    plot = plot + geom_point() + geom_line()

    plot = plot + theme_defaults()
    plot = plot + labs(x="Observed preemption interval (us)", y="Max load (req/s)")
    plot = plot + scale_x_log10() + ylim(0, max_tput)

    ggsave(plot, filename="max_achieved.pdf", width=5.5, height=4, dpi=300)    


    # plot average cost per preemption
    summary_data["slowdown"] = (max_tput - summary_data["achieved"]) / summary_data["achieved"]
    summary_data["cost_per_preempt_us"] = summary_data["slowdown"] * summary_data["observed_interval_us"]

    plot = ggplot(summary_data, aes(x="observed_interval_us", y="cost_per_preempt_us",
        color="preempt_type", linetype="preempt_type"))
    plot = plot + geom_point() + geom_line()

    plot = plot + theme_defaults()
    plot = plot + labs(x="Observed preemption interval (us)", y="Cost per preemption (us)")
    plot = plot + scale_x_log10(limits=[8, 400]) + ylim(0,8)

    ggsave(plot, filename="preemption_cost.pdf", width=5.5, height=4, dpi=300)

def main():
    if len(sys.argv) == 1:
        print("Usage: python3 ./plot_fake_server.py <pattern for CSV files>")
        exit()
    else:
        file_paths = sys.argv[1:]

    all_data = prep_data(file_paths)

    print_columns(all_data)

    if True:
        # plot results for a uniform distribution
        plot_latency_percentile(all_data, "p50")
        plot_latency_percentile(all_data, "p99")
        plot_latency_percentile(all_data, "p99.9")
    else:
        # plot results for a bidodal distribution
        plot_latency_percentile_bimodal(all_data, "p50")
        plot_latency_percentile_bimodal(all_data, "p99")
        plot_latency_percentile_bimodal(all_data, "p99.9")

    # summarize data to get max throughput per config
    summary = all_data.groupby(["preempt_type", "preempt_interval"], as_index=False).agg({
        "achieved": "max",
        "duration": "median",
        "preemptgen": "median"
    })

    #summary = all_data.groupby(["preempt_type", "preempt_interval", "req_type"], as_index=False)["achieved"].agg(max_achieved="max")
    print_entire_df(summary)

    plot_preemption_overhead(summary)

if __name__ == "__main__":
    main()