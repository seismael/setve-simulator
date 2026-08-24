"""Comprehensive End-to-End Manual Environment Validation & Diagnostic Runner.

Executes all 10 STEVE use cases, local cluster simulation, Prometheus HTTP scraping,
and verifies zero-allocation and alignment diagnostics live on the local environment.
"""

from __future__ import annotations

import asyncio
import http.client
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from steve.logging import configure_logging, get_logger
from usecases.usecase_03_prometheus_monitoring import run_prometheus_monitoring


def log_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def run_command_capture(
    cmd: list[str], description: str, cwd: str | None = None
) -> tuple[bool, str, float]:
    """Execute command, capture output, and measure wall-clock duration."""
    t0 = time.perf_counter()
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
        )
        duration = time.perf_counter() - t0
        output = res.stdout + ("\nSTDERR:\n" + res.stderr if res.stderr else "")
        return res.returncode == 0, output.strip(), duration
    except Exception as e:
        duration = time.perf_counter() - t0
        return False, str(e), duration


async def main() -> int:
    configure_logging()
    logger = get_logger("steve.audit.manual")
    repo_root = Path(__file__).resolve().parent.parent

    log_header("STEVE FULL ENVIRONMENT AUDIT & END-TO-END MANUAL VALIDATION")
    logger.info("Starting complete environment validation suite")
    print(f"[*] Python Runtime:     {sys.version.split()[0]} ({sys.platform})")
    print(f"[*] Repository Path:    {repo_root}")
    print(f"[*] Host CPU Cores:     {os.cpu_count() or 1}")
    print(f"[*] Execution Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")

    results: list[dict[str, str | float | bool]] = []

    # -------------------------------------------------------------
    # 1. Run All 10 Production Use Cases
    # -------------------------------------------------------------
    import shutil

    uv_bin = shutil.which("uv") or "uv"

    usecases = [
        ("UC-01: Direct I/O NVMe Stress", "usecase_01_storage_stress.py"),
        ("UC-02: Dedup & Compression", "usecase_02_dedup_compression.py"),
        ("UC-03: Prometheus Live Telemetry", "usecase_03_prometheus_monitoring.py"),
        ("UC-04: eBPF Triangulation", "usecase_04_ebpf_triangulation.py"),
        ("UC-05: AI Vector DB & S3 Ingestion", "usecase_05_ai_vector_s3.py"),
        ("UC-06: LLM KV-Cache Checkpoint", "usecase_06_ai_kv_cache_checkpointing.py"),
        ("UC-07: Multi-Tenant QoS", "usecase_07_multitenant_qos_noisy_neighbor.py"),
        ("UC-08: Distributed Chaos", "usecase_08_chaos_node_failure.py"),
        ("UC-09: Storage Tiering & TCO", "usecase_09_storage_tiering_lifecycle.py"),
        ("UC-10: HDR Tail Latency Microburst", "usecase_10_tail_latency_microburst.py"),
    ]

    log_header("PHASE 1: EXECUTING ALL 10 USE CASES SEQUENTIALLY")
    for name, script_rel in usecases:
        script_path = str(repo_root / "usecases" / script_rel)
        print(f"\n[*] Running {name}...")
        success, out, dur = run_command_capture(
            [uv_bin, "run", "python", script_path], name, cwd=str(repo_root)
        )
        status_str = "PASS" if success else "FAIL"
        print(f"    -> Status: {status_str} in {dur:.2f}s")
        if not success:
            print(f"    [!] Error details:\n{out[:400]}")
        results.append({"name": name, "passed": success, "duration": dur, "output": out})

    # -------------------------------------------------------------
    # 2. Run Local Multi-Node Cluster Emulation
    # -------------------------------------------------------------
    log_header("PHASE 2: LOCAL MULTI-NODE DISTRIBUTED CLUSTER SIMULATION")
    cluster_script = str(repo_root / "deploy" / "emulator" / "cluster_runner.py")
    print("[*] Running 4-Node, 8-Core Cluster with live gRPC barrier sync...")
    cmd = [
        uv_bin,
        "run",
        "python",
        cluster_script,
        "--nodes",
        "4",
        "--cores-per-node",
        "2",
        "--duration",
        "2.0",
    ]
    c_success, c_out, c_dur = run_command_capture(
        cmd, "Local Multi-Node Cluster", cwd=str(repo_root)
    )
    print(f"    -> Cluster Emulation: {'PASS' if c_success else 'FAIL'} in {c_dur:.2f}s")
    results.append(
        {
            "name": "Local Cluster (4-Nodes/8-Cores)",
            "passed": c_success,
            "duration": c_dur,
            "output": c_out,
        }
    )

    # -------------------------------------------------------------
    # 3. Live Prometheus HTTP Server & Socket Client Scrape
    # -------------------------------------------------------------
    log_header("PHASE 3: LIVE PROMETHEUS HTTP SCRAPE & EXPOSITION VALIDATION")
    test_port = 19280
    server_thread = threading.Thread(
        target=run_prometheus_monitoring,
        kwargs={
            "duration_seconds": 1.0,
            "target_throughput_gbps": 2.0,
            "serve_port": test_port,
            "serve_duration": 4.0,
        },
        daemon=True,
    )
    server_thread.start()

    prom_scrape_ok = False
    body = ""
    for _ in range(50):
        time.sleep(0.1)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", test_port, timeout=1.0)
            conn.request("GET", "/metrics")
            resp = conn.getresponse()
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                if "steve_cluster_ops_total" in body:
                    prom_scrape_ok = True
                    print(
                        f"[+] Live HTTP /metrics Scrape OK on port {test_port} ({len(body)} bytes)"
                    )
                    conn.close()
                    break
            conn.close()
        except Exception:
            pass

    server_thread.join(timeout=6.0)

    results.append(
        {
            "name": "Prometheus Live HTTP Socket Scrape",
            "passed": prom_scrape_ok,
            "duration": 1.0,
            "output": "",
        }
    )

    # -------------------------------------------------------------
    # 4. Automated Test Suite (All 62 Tests)
    # -------------------------------------------------------------
    log_header("PHASE 4: AUTOMATED TEST SUITE EXECUTION")
    pytest_cmd = [uv_bin, "run", "pytest", "tests/", "-v"]
    pytest_success, pytest_out, pytest_dur = run_command_capture(
        pytest_cmd,
        "Pytest Full Suite",
        cwd=str(repo_root),
    )
    print(f"[*] Pytest 62 Tests: {'PASS' if pytest_success else 'FAIL'} in {pytest_dur:.2f}s")
    if not pytest_success:
        print(f"    [!] Pytest error details:\n{pytest_out}")
    results.append(
        {
            "name": "Full Pytest Suite (62 tests)",
            "passed": pytest_success,
            "duration": pytest_dur,
            "output": pytest_out,
        }
    )

    # -------------------------------------------------------------
    # Summary Table
    # -------------------------------------------------------------
    log_header("STEVE END-TO-END AUDIT SUMMARY MATRIX")
    print(f"{'Verification Target':<45} | {'Status':<8} | {'Duration'}")
    print("-" * 70)
    all_passed = True
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        if not r["passed"]:
            all_passed = False
        print(f"{str(r['name']):<45} | {status_str:<8} | {float(r['duration']):.2f}s")
    print("-" * 70)
    verdict = "100% PASS - ALL SUBSYSTEMS OPERATIONAL" if all_passed else "FAILURES DETECTED"
    print(f"Overall Result: {verdict}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
