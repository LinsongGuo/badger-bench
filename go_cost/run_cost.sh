#!/bin/bash

# Define combinations of (numget, numscan)
combinations=(
    "0 1"
    "1 0"
    "0 2"
    "0 3"
    "0 4"
    "0 8"
    "1 1"
    "2 2"
    "3 3"
    "4 4"
    "8 8"
)

# Define quantum values
quantum_values=(1000000 10000 1000 100 50 20 10 5)

# Number of times to repeat each command
repeat=15

# Base directory for results
result_dir="result/signal"

# Create the base directory if it doesn't exist
mkdir -p "$result_dir"

/data/preempt/go/go-preempt/bin/go build main.go

# Loop through each (numget, numscan) combination
for combo in "${combinations[@]}"; do
    read -r numget numscan <<< "$combo"

    combination_dir="$result_dir/${numget}get+${numscan}scan"
    mkdir -p "$combination_dir"

    for quantum in "${quantum_values[@]}"; do
        # Convert GOFORCEPREEMPTNS value (quantum * 1000)
        goforcepreemptns=$((quantum * 1000))

        quantum_dir="$combination_dir/$quantum"
        mkdir -p "$quantum_dir"

        echo "${numget}get+${numscan}scan ($quantum us)"

        # Repeat the command 9 times
        for i in $(seq 1 $repeat); do
            output_file="$quantum_dir/$i"

            # Run the command and save output (stdout + stderr)
            GOMAXPROCS=1 PREEMPT_INFO=1 GOFORCEPREEMPTNS=$goforcepreemptns \
            numactl --cpunodebind=0 --membind=0 ./main \
            --dir /data/preempt/go/db_data/ --keys_mil 250 --valsz 64 \
            --get $numget --scan $numscan > "$output_file" 2>&1
        done
    done
done

echo "Experiment completed. Results saved in 'result/' directory."
