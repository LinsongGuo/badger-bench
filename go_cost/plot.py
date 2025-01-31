import os
import re
import numpy as np
import matplotlib.pyplot as plt

# Define main directory paths
MAIN_DIR = os.getcwd()
RESULT_DIR = f"{MAIN_DIR}/result/signal"

# Define combinations and quantum values to show
combinations = [(0, 1), (1, 0), (0, 2), (0, 3), (0, 4), (0, 8), (1, 1), (2, 2), (3, 3), (4, 4), (8, 8)]
quantum_values = [100, 50, 20, 10, 5]  
TRIAL = 15  # Number of trials per experiment

# Function to extract runtime and total preemptgen from log file
def extract_values(log_file):
    runtime, total_preemptgen = None, None
    with open(log_file, "r") as f:
        for line in f:
            if match := re.search(r"Runtime:\s+(\d+)\s+us", line):
                runtime = int(match.group(1))
            elif match := re.search(r"Total preemptgen:\s+(\d+)", line):
                total_preemptgen = int(match.group(1))
    return runtime, total_preemptgen

# Function to compute median runtime and its corresponding preemptgen
def compute_median_runtime_preemptgen(runtimes_preemptgens):
    if not runtimes_preemptgens:
        return None, None  # No data available

    # Sort by runtime
    runtimes_preemptgens.sort(key=lambda x: x[0])  

    # Compute median index
    median_index = len(runtimes_preemptgens) // 2
    if len(runtimes_preemptgens) % 2 == 0:
        median_index -= 1  # Take lower median for even count

    return runtimes_preemptgens[median_index]  # Return (runtime, preemptgen)

# Extract get_base (1get+0scan/1000000) and scan_base (0get+1scan/1000000)
def get_base_values():
    get_base_runtime, _ = extract_values(f"{RESULT_DIR}/1get+0scan/1000000/1")
    scan_base_runtime, _ = extract_values(f"{RESULT_DIR}/0get+1scan/1000000/1")
    return get_base_runtime, scan_base_runtime

get_base, scan_base = get_base_values()

# Collect cost data for plotting
data = {combo: [] for combo in combinations}

for numget, numscan in combinations:
    for quantum in quantum_values:
        quantum_dir = f"{RESULT_DIR}/{numget}get+{numscan}scan/{quantum}"

        # Collect (runtime, preemptgen) pairs
        runtimes_preemptgens = []
        for i in range(1, TRIAL + 1):
            log_file = f"{quantum_dir}/{i}"
            if os.path.exists(log_file):
                runtime, preemptgen = extract_values(log_file)
                if runtime is not None and preemptgen is not None and preemptgen > 0:  # Avoid division by zero
                    runtimes_preemptgens.append((runtime, preemptgen))
            else:
                print(f"not exist: {log_file}!")

        # Compute median runtime and corresponding preemptgen
        median_runtime, median_preemptgen = compute_median_runtime_preemptgen(runtimes_preemptgens)

        if median_runtime is not None and median_preemptgen > 0:
            # Calculate base_runtime
            base_runtime = (numget * get_base) + (numscan * scan_base)

            # Compute cost
            cost = (median_runtime - base_runtime) / median_preemptgen
            data[(numget, numscan)].append(cost)
        else:
            data[(numget, numscan)].append(0)  # Default to 0 if no valid data

# Plot grouped bar chart
fig, ax = plt.subplots(figsize=(18, 6))

bar_width = 0.15  # Controls spacing between bars
x = np.arange(len(combinations))  # X-axis positions for groups

# Define colors for different quantum values
colors = plt.cm.viridis(np.linspace(0, 1, len(quantum_values)))

# Plot bars for each quantum value
for idx, quantum in enumerate(quantum_values):
    costs = [data[combo][idx] for combo in combinations]  # Get data for this quantum
    ax.bar(x + idx * bar_width, costs, bar_width, label=f"Quantum {quantum}", color=colors[idx])

# Formatting
ax.set_xticks(x + bar_width * (len(quantum_values) / 2))
ax.set_xticklabels([f"{numget}get+{numscan}scan" for numget, numscan in combinations], rotation=45, ha="right")
ax.set_ylabel("Cost (us/preemption)")
ax.set_xlabel("Experiment Combinations (numget + numscan)")
ax.set_title("Cost for Different (numget, numscan) Combinations and Quantum Values")
ax.legend(title="Signal-Quantum")

plt.xticks(rotation=45, ha="right")
plt.tight_layout()

# Show the plot
plt.show()
plt.savefig('figure.pdf')