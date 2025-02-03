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
repeat=59
mechanisms=(signal uintr compiler)
# mechanisms=(compiler_separate)
input_dir="/data/preempt/go/db_data/"

/data/preempt/go/go-preempt/bin/go build main.go

for i in $(seq 43 $repeat); do
    for mech in "${mechanisms[@]}"; do
        result_dir="result/$mech"
        mkdir -p "$result_dir"

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
                output_file="$quantum_dir/$i"

                echo "${numget}get+${numscan}scan ($quantum us) $i"  

                use_uintr=0
                if [[ "$mech" == "uintr" ]]; then
                    use_uintr=1
                fi           
                
                if [[ "$mech" == "compiler" ]]; then
                    GODEBUG=asyncpreemptoff=1 GOMAXPROCS=1 PREEMPT_INFO=1 UINTR=$use_uintr GOFORCEPREEMPTNS=$goforcepreemptns \
                    numactl --cpunodebind=0 --membind=0 ./main \
                    --dir $input_dir --keys_mil 250 --valsz 64 \
                    --get $numget --scan $numscan > "$output_file" 2>&1
                else
                    GOMAXPROCS=1 PREEMPT_INFO=1 UINTR=$use_uintr GOFORCEPREEMPTNS=$goforcepreemptns \
                    numactl --cpunodebind=0 --membind=0 ./main \
                    --dir $input_dir --keys_mil 250 --valsz 64 \
                    --get $numget --scan $numscan > "$output_file" 2>&1
                fi
            done
        done
    done
done

echo "Experiment completed. Results saved in 'result/' directory."
