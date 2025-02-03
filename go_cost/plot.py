import os
import re
import numpy as np
import matplotlib.pyplot as plt

# Define main directory paths
MAIN_DIR = os.getcwd()
RESULT_DIR = f"{MAIN_DIR}/result"

# Define combinations and quantum values to show
combinations = [(0, 1),(0, 2), (0, 3), (0, 4), (0, 8), (1, 1), (2, 2), (3, 3), (4, 4), (8, 8)]
quantum_values = [100, 50, 20, 10, 5]  
all_quantum_values = [1000000, 100, 50, 20, 10, 5]  
TRIAL = 9  # Number of trials per experiment
mechanisms = ['signal', 'uintr', 'compiler']
# mechanisms = ['signal', 'uintr']

# Function to extract runtime and total preemptgen from log file
def extract_values(log_file, mech):
    runtime, total_preemptgen, total_preemptgensync = None, None, None
    with open(log_file, "r") as f:
        for line in f:
            if match := re.search(r"Runtime:\s+(\d+)\s+us", line):
                runtime = int(match.group(1))
            elif match := re.search(r"Total preemptgen:\s+(\d+)", line):
                total_preemptgen = int(match.group(1))
            elif match := re.search(r"Total synchronous preemptgen:\s+(\d+)", line):
                total_preemptgensync = int(match.group(1))
    if mech == 'compiler':
        return runtime, total_preemptgensync
    else:
        return runtime, total_preemptgen

# Function to compute median runtime and its corresponding preemptgen
def compute_median_runtime_preemptgen(runtimes_preemptgens):
    if not runtimes_preemptgens:
        return None, None  # No data available

    # Sort by runtime
    runtimes_preemptgens.sort(key=lambda x: x[0])  
    median_index = len(runtimes_preemptgens) // 2
    if len(runtimes_preemptgens) % 2 == 0:
        median_index -= 1  # Take lower median for even count

    return runtimes_preemptgens[median_index]  # Return (runtime, preemptgen)

def compute_median_runtime(runtimes):
    if not runtimes:
        return None  # No data available
    runtimes.sort()
    median_index = len(runtimes) // 2
    if len(runtimes) % 2 == 0:
        median_index -= 1  # Take lower median for even count
    return runtimes[median_index]

# # Extract get_base (1get+0scan/1000000) and scan_base (0get+1scan/1000000) for both mechanisms using median
def get_base_values(mechanism):
    get_runtimes = []
    scan_runtimes = []

    # trial = 5 if mechanism == 'uintr' else TRIAL
    trial = TRIAL
    for i in range(1, trial + 1):
        get_file = f"{RESULT_DIR}/{mechanism}/1get+0scan/1000000/{i}"
        scan_file = f"{RESULT_DIR}/{mechanism}/0get+1scan/1000000/{i}"
        # get_file = f"{RESULT_DIR}/{mechanism}/1get+0scan/10000/{i}"
        # scan_file = f"{RESULT_DIR}/{mechanism}/0get+1scan/10000/{i}"

        if os.path.exists(get_file):
            runtime, _ = extract_values(get_file, mechanism)
            if runtime is not None:
                get_runtimes.append(runtime)

        if os.path.exists(scan_file):
            runtime, _ = extract_values(scan_file, mechanism)
            if runtime is not None:
                scan_runtimes.append(runtime)

    get_base_runtime = compute_median_runtime(get_runtimes)
    scan_base_runtime = compute_median_runtime(scan_runtimes)

    return get_base_runtime, scan_base_runtime

base_values = {mech: get_base_values(mech) for mech in mechanisms}

# Collect cost data for both mechanisms
data = {combo: {mech: [] for mech in mechanisms} for combo in combinations}

for numget, numscan in combinations:
    for mechanism in mechanisms:
        base_runtime = None
        for quantum in all_quantum_values:
            quantum_dir = f"{RESULT_DIR}/{mechanism}/{numget}get+{numscan}scan/{quantum}"

            # Collect (runtime, preemptgen) pairs
            # trial = 5 if mechanism == 'uintr' else TRIAL
            # trial = 11 if mechanism=='compiler' else (35 if numget>0 and numscan>0 else TRIAL)
            trial = TRIAL
            runtimes_preemptgens = []
            for i in range(1, trial + 1):
                log_file = f"{quantum_dir}/{i}"
                if os.path.exists(log_file):
                    runtime, preemptgen = extract_values(log_file, mechanism)
                    if runtime is not None and preemptgen is not None:
                        runtimes_preemptgens.append((runtime, preemptgen))
                else:
                    print(f"not exist: {log_file}!")

            # Compute median runtime and corresponding preemptgen
            median_runtime, median_preemptgen = compute_median_runtime_preemptgen(runtimes_preemptgens)

            if quantum == 1000000:
                base_runtime = median_runtime
                # print(f"{mechanism}, {numget}get+{numscan}scan/{quantum}: {base_runtime}")
            else:     
                if median_runtime is not None and median_preemptgen > 0:
                    # get_base, scan_base = base_values[mechanism]
                    
                    # Calculate base_runtime
                    # base_runtime = numscan * scan_base + numget * get_base

                    # Compute cost
                    cost = (median_runtime - base_runtime) / median_preemptgen
                    data[(numget, numscan)][mechanism].append(cost)
                else:
                    data[(numget, numscan)][mechanism].append(0)  # Default to 0 if no valid data

# Plot grouped bar chart
fig, ax = plt.subplots(figsize=(15, 6))

bar_width = 0.15  # Controls spacing between bars
x = np.arange(len(combinations))  # X-axis positions for groups

# Define colors for different quantum values and mechanisms
colors = plt.cm.viridis(np.linspace(0, 1, len(quantum_values)))

# Plot bars for each quantum value and mechanism
for idx, quantum in enumerate(quantum_values):
    for mech_idx, mech in enumerate(mechanisms):
    # for mech in ['signal']:
        costs = [data[combo][mech][idx] for combo in combinations]  # Get data for this quantum
        ax.bar(x + (idx * bar_width) + mech_idx*0.05, 
               costs, bar_width/3, label=f"{mech}-{quantum}", color=colors[idx], alpha=0.75)

# Formatting
ax.set_xticks(x + bar_width * (len(quantum_values) / 2))
ax.set_xticklabels([f"{numget}get+{numscan}scan" for numget, numscan in combinations], rotation=45, ha="right")
ax.set_ylim(bottom=0, top=8)
ax.set_ylabel("Cost (us/preemption)")
ax.set_xlabel("Experiment Combinations (numget + numscan)")
ax.set_title("Cost for Different (numget, numscan) Combinations and Quantum Values")
ax.legend(title="Mechanism-Quantum")

plt.xticks(rotation=45, ha="right")
plt.tight_layout()

# Show the plot
plt.show()
plt.savefig('figure.pdf')
