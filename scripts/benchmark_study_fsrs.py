#!/usr/bin/env python3
"""
Sovereign Study Commons India - Standalone FSRS-5 Continuous Memory Benchmark Reproducer
Runs 2,000 evaluations of continuous retrievability:
R(t, S) = (1 + (19/81) * (t / S))^(-0.5)
Measures:
- Average Latency (µs)
- p95 Latency (µs)
- Throughput (Evals/sec)
"""

import statistics
import time

CARDS = [(float(i % 30 + 1), float(i % 10 + 2.5)) for i in range(100)]

def run_benchmark(rounds: int = 2000):
    print("======================================================================")
    print("⚡ STUDY COMMONS FSRS-5 RETRIEVABILITY BENCHMARK REPRODUCER (Apple Silicon M1)")
    print("======================================================================")

    latencies = []
    factor = 19.0 / 81.0

    for i in range(rounds):
        t_days, S_stability = CARDS[i % len(CARDS)]
        t0 = time.perf_counter_ns()
        
        # FSRS-5 continuous retention equation
        retrievability = (1.0 + factor * (t_days / S_stability)) ** -0.5
        due = retrievability < 0.90
        
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0) / 1000.0)

    avg_lat = statistics.mean(latencies)
    p95_lat = sorted(latencies)[int(0.95 * len(latencies))]
    ops_sec = 1_000_000.0 / avg_lat

    print(f"• Total FSRS-5 Evals    : {rounds}")
    print(f"• Average Latency       : {avg_lat:.3f} µs")
    print(f"• p95 Latency           : {p95_lat:.3f} µs")
    print(f"• Throughput            : {ops_sec:,.1f} evals/sec")
    print(f"• Baseline Target       : ~3,752,507.1 evals/sec (avg ~0.266 µs)")
    print("======================================================================")
    return True

if __name__ == "__main__":
    run_benchmark(2000)
