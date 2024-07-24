import argparse
import os
import psutil
import re
import subprocess
import sys
import time
from datetime import datetime
from enum import Enum, auto

latency_percentiles = [50, 90, 99, 99.9, 100]
fields = ["preempt_type", "preempt_interval", "target", "achieved", "req_type", "duration", "preemptgen"]
next_port = 3000

lua_scripts = {
    #1: "uniform_1us.lua",
    #10: "uniform_10us.lua",
    #100: "uniform_100us.lua",
    #10000: "uniform_10ms.lua"
    "short": "short.lua"
}

class PreemptType(Enum):
    SIGNAL = auto()
    UINTR = auto()

    def __str__(self):
        return self.name.lower()

def exec_cmd(cmd):
    result = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

def new_experiment(cores, collect_traces, avg_service_time_us, bimodal,
                   preempt_type, preempt_interval):
    preempt_interval_str = str(int(preempt_interval / 1000)) + "us"

    if bimodal:
        lua_script = ""
    elif avg_service_time_us not in lua_scripts.keys():
        print(f"Unrecognized service time {avg_service_time_us}us")
        sys.exit()
    else:
        lua_script = lua_scripts[avg_service_time_us]

    exp = {
        'name': "run.{}-{}-{}".format(datetime.now().strftime("%Y%m%d%H%M%S"),
                                      preempt_type, preempt_interval_str),
        'cores': cores,
        'collect_traces': collect_traces,
        'avg_service_time_us': avg_service_time_us,
        'workload_file': lua_script,
        'bimodal': bimodal,
        'preempt_type': preempt_type,
        'preempt_interval': preempt_interval,
        'preempt_interval_str': preempt_interval_str,
        }

    os.mkdir(exp['name'])

    # copy some files into the results directory for the record
    with open(f"{exp['name']}/experiment.txt", "w") as f:
        f.write(str(exp) + "\n")
    if not bimodal:
        exec_cmd(f"cp {lua_script} {exp['name']}/")
    exec_cmd(f"cp wrk_runner.py {exp['name']}/")

    return exp

def results_file(exp):
    return f"{exp['name']}/results_{exp['preempt_interval_str']}.csv"

def server_output_file(exp):
    return f"{exp['name']}/server_{exp['current_port']}.out"

def start_trace(exp):
    exec_cmd(f"sudo kill -SIGUSR1 {exp['server_pid']}")

def stop_trace(exp):
    exec_cmd(f"sudo kill -SIGUSR2 {exp['server_pid']}")

def summarize_wrk_results(target_rate, wrk):
    results_dict = {}
    results_dict["target"] = target_rate
    results_dict["req_type"] = wrk.req_type

    for l in wrk.stdout.split("\n"):
        pattern = r"(\d+\.\d+)%\s+(\d+\.\d+)(.?s)"
        match = re.search(pattern, l)
        if match:
            percentage = float(match.group(1))
            time_units = match.group(3)
            t = float(match.group(2))
            if time_units == "ms":
                t = t * 1000
            elif time_units == "s":
                t = t * 1000 * 1000
            elif time_units != "us":
                # unrecognized units, leave the whole string
                t = match.group(2)
            results_dict[percentage] = t

        pattern = r"Requests/sec:\s+(\d+\.\d+)"
        match = re.search(pattern, l)
        if match:
            results_dict["achieved"] = match.group(1)

    return results_dict

def parse_server_output(output_file):
    results_dict = {}

    with open(output_file, "r") as f:
        for l in f:
            pattern = "executing for (\d+\.\d+) seconds"
            match = re.search(pattern, l)
            if match:
                results_dict["duration"] = float(match.group(1))

            pattern = r"total preemptgen: (\d+)"
            match = re.search(pattern, l)
            if match:
                results_dict["preemptgen"] = int(match.group(1))

    return results_dict

def start_server(exp):
    global next_port

    exp['current_port'] = next_port
    next_port += 1

    env = f"GOMAXPROCS={exp['cores']} PREEMPT_INFO=1 GOFORCEPREEMPTNS={exp['preempt_interval']} "
    if exp["preempt_type"] == PreemptType.UINTR:
        env += "UINTR=1 "
    cmd = f'numactl --cpunodebind 0 ./badger-server --keys_mil 250 --valsz 128 -port={exp["current_port"]} -run={exp["name"]} -dir="/data/dzuberi/db_data"'
    if exp['collect_traces']:
        cmd += " -trace"
    output = f" 2>&1 | ts %s > {server_output_file(exp)}"
    proc = subprocess.Popen(env + cmd + output, shell=True)

    # let the server start
    time.sleep(90)

    # fetch the PID for the server
    pids = get_pids("badger-server")
    exp['server_pid'] = pids[0]

    return proc

def get_pids(process_name):
    pids = []

    for proc in psutil.process_iter(['pid', 'name']):
        if process_name in proc.info['name']:
            pids.append(proc.info['pid'])

    return pids

def stop_server(s):
    s.terminate()
    s.wait()
    del s

    pids = get_pids("badger-server")
    for pid in pids:
        exec_cmd(f"sudo kill {pid}")

# an instance of a wrk load-generating process
class Wrk:
    def __init__(self, command, request_type):
        self.cmd = command
        self.req_type = request_type

def benchmark_data_point(exp, target_rate):
    # start the server
    s = start_server(exp)

    try:
        start_trace(exp)

        wrks = []

        if not exp['bimodal']:
            command = f"wrk_ds -t12 -c12 -d20s -R{target_rate} -s {exp['workload_file']} --dist exp --latency http://127.0.0.1:{exp['current_port']}"

            wrk = Wrk(command, str(exp['avg_service_time_us']))
            wrks.append(wrk)

            print(f"Running benchmark with command {command}")

            wrk.proc = subprocess.Popen(command, shell=True, text=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        else:
            # assume 95% short, 5% long
            # 12 wrk threads and conns for short, 1 thread and conn for long
            short_rate = int(target_rate * 0.95)
            command_short = f"wrk_ds -t12 -c12 -d20s -R{short_rate} -s uniform_1us.lua --dist exp --latency http://127.0.0.1:{exp['current_port']}"
            wrk = Wrk(command_short, "1us")
            wrks.append(wrk)

            print(f"Running wrk for short requests with command {command_short}")
            wrk.proc = subprocess.Popen(command_short, shell=True, text=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

            long_rate = int(target_rate * 0.05)
            command_long = f"wrk_ds -t1 -c1 -d20s -R{long_rate} -s uniform_260us.lua --dist exp --latency http://127.0.0.1:{exp['current_port']}"
            wrk = Wrk(command_long, "260us")
            wrks.append(wrk)

            print(f"Running wrk for long requests with command {command_long}")
            wrk.proc = subprocess.Popen(command_long, shell=True, text=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

        for wrk in wrks:
            wrk.stdout, wrk.stderr = wrk.proc.communicate()
        stop_trace(exp)

        # stop the server
        stop_server(s)

        for wrk in wrks:
            with open(f"{exp['name']}/output_{target_rate}_{wrk.req_type}.stdout", "w") as f:
                f.write(wrk.stdout)
            with open(f"{exp['name']}/output_{target_rate}_{wrk.req_type}.stderr", "w") as f:
                f.write(wrk.stderr)

            # aggregate results
            all_results = exp.copy()

            # parse the output from the server
            server_results = parse_server_output(server_output_file(exp))
            all_results.update(server_results)

            # parse and summarize the results
            wrk_results = summarize_wrk_results(target_rate, wrk)
            all_results.update(wrk_results)

            # write results to file
            with open(results_file(exp), "a") as f_out:
                all_output_fields = fields + latency_percentiles
                f_out.write(",".join([str(all_results.get(x)) for x in all_output_fields]) + "\n")

    except subprocess.CalledProcessError as e:
            print(f"Benchmark failed with return code {e.returncode}")

# compute offered loads for a given experiment
def offered_loads(exp):
    min_load = 0

    if exp['cores'] == 1:
        # config for 1 proc
        if exp['bimodal']:
            max_load = 60 * 1000
        else:
            max_load = 400 * 1000
        num_steps = 10
        step_size = int((max_load - min_load) / num_steps)
    else:
        print(f"warning: rates may not be optimal for {exp['cores']} cores")
        max_load = 40 * 1000 * exp['cores']
        num_steps = 8
        step_size = int((max_load - min_load) / num_steps)

    return [min_load + step_size * (i + 1) for i in range(num_steps)]

def benchmark_system(cores, collect_traces, avg_service_time_us, bimodal, preempt_type,
                     preempt_interval):
    print(f"Benchmarking with preemption {preempt_type} and interval {preempt_interval}ns")

    # create the experiment and a directory for it
    exp = new_experiment(cores, collect_traces, avg_service_time_us, bimodal,
                         preempt_type, preempt_interval)

    with open(results_file(exp), "w") as f_out:
        hdr_str = ",".join(fields + ["p" + str(x) for x in latency_percentiles])
        f_out.write(f"{hdr_str}\n")

    # run the wrk client at several different loads
    for rate in offered_loads(exp):
        benchmark_data_point(exp, rate)

        # sleep briefly between data points
        time.sleep(1)

    # generate PNGs for all CPU profiles
    for filename in os.listdir(exp['name']):
        if filename.endswith(".prof"):
            png_filename = filename.replace(".prof", ".png")
            exec_cmd(f"go tool pprof -png -output {exp['name']}/{png_filename} {exp['name']}/{filename}")

def main():
    parser = argparse.ArgumentParser(description='run basic go server experiments')

    parser.add_argument('-c', '--cores', type=int, default=1, help='number of cores')
    parser.add_argument('-uintr', action="store_true", help='run with user interrupts')
    parser.add_argument('-signal', action="store_true", help='run with signals')
    parser.add_argument('-trace', action="store_true", help='run with traces')
    parser.add_argument('-bimodal', action="store_true", help='use a bimodal distribution')
    args = parser.parse_args()

    start_time = datetime.now()

    avg_service_time_us = 'short'
    # target_intervals = [10 * 1000 * 1000, 100 * 1000, 10 * 1000]
    target_intervals = [1000]
    for interval in target_intervals:
        if args.uintr:
            benchmark_system(args.cores, args.trace, avg_service_time_us, args.bimodal,
                             PreemptType.UINTR, interval)
        if args.signal:
            benchmark_system(args.cores, args.trace, avg_service_time_us, args.bimodal,
                             PreemptType.SIGNAL, interval)

    duration = datetime.now() - start_time
    print(f"Total experiment runtime: {duration.total_seconds()} seconds")

if __name__ == "__main__":
    main()