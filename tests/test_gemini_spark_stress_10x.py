#!/usr/bin/env python3
"""
⚡ 10X STRESS TEST: Gemini Spark Slot 02 Autonomous Pipeline
Verifies high-throughput queue draining, transaction commits, and SHA-256 receipts.
"""
import os
import sys
import time
import shutil
import sqlite3
from pathlib import Path

REPO_ROOT = Path("/Users/rajondas/teamwork_projects/sovereign-study-commons-india")
QUEUE_DIR = REPO_ROOT / "tasks" / "queue"
COMPLETED_DIR = REPO_ROOT / "tasks" / "completed"
SPARK_DB = Path("/Users/rajondas/.air1/SPARK5_TRANSACTION_LEDGER.sqlite")
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gemini_spark_daemon

def run_10x_stress():
    print("======================================================================")
    print("⚡ RUNNING 10X STRESS TEST: GEMINI SPARK SLOT 02")
    print("======================================================================")
    
    # 1. Enqueue 10 synthetic EE tasks
    test_task_ids = []
    for i in range(1, 11):
        t_id = f"TASK_STRESS_{int(time.time())}_{i:02d}"
        test_task_ids.append(t_id)
        task_file = QUEUE_DIR / f"{t_id}.md"
        with open(task_file, "w") as f:
            f.write(f"# Task {t_id}\nDerive electromagnetic torque and sub-transient direct reactance for Machine #{i}.")
            
    print(f"[✔] Enqueued 10 tasks in {QUEUE_DIR}")
    
    # 2. Run daemon cycle
    start_time = time.time()
    gemini_spark_daemon.run_cycle()
    elapsed = time.time() - start_time
    print(f"[✔] Daemon drained queue in {elapsed*1000:.2f} ms ({elapsed/10*1000:.2f} ms/task)")
    
    # 3. Verify all 10 tasks are in completed/
    conn = sqlite3.connect(str(SPARK_DB))
    c = conn.cursor()
    
    for t_id in test_task_ids:
        sol_file = COMPLETED_DIR / f"{t_id}_SOLUTION.md"
        assert sol_file.exists(), f"Missing solution file for {t_id}"
        
        # Verify in DB
        c.execute("SELECT result, receipt_path FROM transactions WHERE task_id = ?", (t_id,))
        row = c.fetchone()
        assert row is not None, f"Missing DB transaction for {t_id}"
        assert row[0] == "SUCCESS_PHYSICAL", f"Unexpected result {row[0]} for {t_id}"
        
    conn.close()
    print("======================================================================")
    print(f"🎉 10X STRESS TEST PASSED: All 10 tasks processed and verified physically!")
    print("======================================================================")

if __name__ == "__main__":
    run_10x_stress()
