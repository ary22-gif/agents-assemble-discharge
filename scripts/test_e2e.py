#!/usr/bin/env python3
"""
End-to-end test — starts all five servers, fires an A2A discharge request,
validates the response structure, prints a rich terminal summary.

Usage:
    uv run python scripts/test_e2e.py [patient-001|patient-002|patient-003]

Requires:
    - GEMINI_API_KEY in environment or .env file
    - All ports 8000-8004 free

DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.
"""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv()
console = Console()

ROOT = Path(__file__).parent.parent
PATIENT = sys.argv[1] if len(sys.argv) > 1 else "patient-001"
FHIR_URL = os.getenv("FHIR_BASE_URL", "http://localhost:8000/fhir")
API_KEY = os.getenv("AGENT_API_KEY", "demo-key-e2e")
BASE_URL = os.getenv("A2A_BASE_URL", "http://localhost")

SERVERS = [
    {
        "name": "FHIR Server",
        "cmd": [
            "uv",
            "run",
            "uvicorn",
            "fhir_server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        "health": "http://127.0.0.1:8000/health",
        "port": 8000,
    },
    {
        "name": "MedRecon Agent",
        "cmd": [
            "uv",
            "run",
            "uvicorn",
            "agents.medrecon.app:a2a_app",
            "--host",
            "127.0.0.1",
            "--port",
            "8002",
        ],
        "health": "http://127.0.0.1:8002/.well-known/agent-card.json",
        "port": 8002,
    },
    {
        "name": "CarePlan Agent",
        "cmd": [
            "uv",
            "run",
            "uvicorn",
            "agents.careplan.app:a2a_app",
            "--host",
            "127.0.0.1",
            "--port",
            "8003",
        ],
        "health": "http://127.0.0.1:8003/.well-known/agent-card.json",
        "port": 8003,
    },
    {
        "name": "FollowUp Agent",
        "cmd": [
            "uv",
            "run",
            "uvicorn",
            "agents.followup.app:a2a_app",
            "--host",
            "127.0.0.1",
            "--port",
            "8004",
        ],
        "health": "http://127.0.0.1:8004/.well-known/agent-card.json",
        "port": 8004,
    },
    {
        "name": "Orchestrator Agent",
        "cmd": [
            "uv",
            "run",
            "uvicorn",
            "agents.orchestrator.app:a2a_app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        "health": "http://127.0.0.1:8001/.well-known/agent-card.json",
        "port": 8001,
    },
]

FHIR_EXTENSION_URI = os.getenv(
    "FHIR_EXTENSION_URI",
    "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context",
)


def check_api_key():
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        console.print(
            "[bold red]ERROR:[/] GEMINI_API_KEY not set. Copy .env.example → .env and add your key."
        )
        sys.exit(1)


def start_server(spec: dict, env: dict) -> subprocess.Popen:
    proc = subprocess.Popen(
        spec["cmd"],
        cwd=str(ROOT),
        env={**os.environ, **env},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


def wait_healthy(url: str, name: str, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def build_a2a_request(patient_id: str, fhir_token: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": f"Prepare discharge packet for patient {patient_id}.",
                    }
                ],
                "metadata": {
                    FHIR_EXTENSION_URI: {
                        "fhirUrl": FHIR_URL,
                        "fhirToken": fhir_token,
                        "patientId": patient_id,
                    }
                },
            }
        },
    }


def extract_response_text(data: dict) -> str:
    result = data.get("result", {})
    artifacts = result.get("artifacts", [])
    if artifacts:
        parts = artifacts[0].get("parts", [])
        if parts:
            return parts[0].get("text", "")
    status = result.get("status", {})
    msg = status.get("message", {})
    parts = msg.get("parts", [])
    if parts:
        return parts[0].get("text", "")
    return json.dumps(result)


def parse_packet(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except Exception:
        return {"status": "parse_error", "raw": text[:500]}


def validate_packet(packet: dict) -> list[str]:
    issues = []
    if packet.get("status") != "success":
        issues.append(
            f"top-level status is '{packet.get('status')}', expected 'success'"
        )
    for section in ("medications", "care_instructions", "follow_up"):
        if section not in packet:
            issues.append(f"missing section: {section}")
        elif packet[section].get("status") != "success":
            issues.append(
                f"{section}.status = '{packet[section].get('status')}' (may be LLM/FHIR error)"
            )
    if not packet.get("provenance"):
        issues.append("provenance list is empty — citation tracking may be broken")
    if not packet.get("agent_timings"):
        issues.append("agent_timings missing")
    disclaimer = packet.get("disclaimer", "")
    if "SYNTHETIC" not in disclaimer and "DEMO" not in disclaimer:
        issues.append("disclaimer missing from packet")
    return issues


def print_summary(packet: dict, duration_s: float, issues: list[str]):
    console.print()
    console.rule("[bold cyan]DISCHARGE COORDINATOR — E2E TEST RESULTS[/]")
    console.print(f"[dim]{packet.get('disclaimer', '')}[/dim]\n")

    # Patient header
    console.print(
        Panel(
            f"[bold]{packet.get('patient_name', '?')}[/]  |  Patient ID: {packet.get('patient_id', '?')}\n"
            f"Generated: {packet.get('generated_at', '?')}",
            title="Patient",
            border_style="cyan",
        )
    )

    # Agent timings
    timing_table = Table(title="Agent Timings", box=box.SIMPLE_HEAVY)
    timing_table.add_column("Agent", style="bold")
    timing_table.add_column("Duration", justify="right")
    timing_table.add_column("Status")
    for t in packet.get("agent_timings", []):
        color = "green" if t["status"] == "success" else "red"
        timing_table.add_row(
            t["agent"],
            f"{t['duration_ms']:.0f} ms",
            f"[{color}]{t['status']}[/{color}]",
        )
    timing_table.add_row(
        "[bold]TOTAL (wall)[/]", f"[bold]{duration_s * 1000:.0f} ms[/]", ""
    )
    console.print(timing_table)

    # Medications summary
    meds = packet.get("medications", {})
    if meds.get("status") == "success":
        med_table = Table(
            title=f"Medications ({meds.get('total_active_medications', '?')} active)",
            box=box.SIMPLE,
        )
        med_table.add_column("Medication")
        med_table.add_column("Action")
        med_table.add_column("Resource ID", style="dim")
        for m in meds.get("reconciled_medications", []):
            med_table.add_row(
                m.get("medication_name", "?"),
                m.get("action", "?"),
                m.get("resource_id", "?"),
            )
        console.print(med_table)

        interactions = meds.get("drug_interactions", [])
        if interactions:
            console.print(
                f"[yellow]⚠  {len(interactions)} drug interaction(s) flagged:[/]"
            )
            for ix in interactions:
                color = "red" if ix["severity"] == "major" else "yellow"
                console.print(
                    f"  [{color}][{ix['severity'].upper()}][/{color}] {ix['description'][:100]}…"
                )
        if meds.get("polypharmacy_flag"):
            console.print("[yellow]⚠  Polypharmacy flag: ≥5 active medications[/]")

    # Follow-up gaps
    fu = packet.get("follow_up", {})
    if fu.get("status") == "success":
        gaps = fu.get("pending_referrals", [])
        sched = fu.get("scheduled_appointments", [])
        console.print(
            f"\n[bold]Follow-Up:[/] {len(sched)} scheduled, [red]{len(gaps)} gaps[/]"
        )
        for g in gaps:
            color = "red" if g.get("priority") == "urgent" else "yellow"
            console.print(
                f"  [{color}]● {g.get('referral_type', '?')} — {g.get('suggested_window', '?')} [{g.get('priority', '?').upper()}][/{color}]"
            )

    # Care instructions preview
    care = packet.get("care_instructions", {})
    if care.get("status") == "success":
        console.print(
            f"\n[bold]Primary Diagnosis:[/] {care.get('primary_diagnosis', '?')}"
        )
        red_flags = care.get("red_flag_symptoms", [])
        if red_flags:
            console.print(f"[bold]Red flags:[/] {len(red_flags)} symptoms listed")

    # Provenance
    prov = packet.get("provenance", [])
    console.print(f"\n[bold]Provenance:[/] {len(prov)} FHIR resource citations")

    # Validation
    console.print()
    if issues:
        console.print(
            Panel(
                "\n".join(f"  ❌ {i}" for i in issues),
                title="[bold red]Validation Issues[/]",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                "[bold green]✅ All validation checks passed[/]", border_style="green"
            )
        )

    console.rule()


def main():
    check_api_key()

    env_extra = {
        "AGENT_API_KEY": API_KEY,
        "FHIR_BASE_URL": "http://127.0.0.1:8000/fhir",
        "A2A_BASE_URL": "http://127.0.0.1",
        "MEDRECON_URL": "http://127.0.0.1:8002",
        "CAREPLAN_URL": "http://127.0.0.1:8003",
        "FOLLOWUP_URL": "http://127.0.0.1:8004",
        "ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS": "true",
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
    }

    procs = []

    try:
        console.print(
            Panel(
                f"[bold]Patient:[/] {PATIENT}\n"
                f"[bold]FHIR URL:[/] http://127.0.0.1:8000/fhir\n"
                "[dim]DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.[/dim]",
                title="[bold cyan]Discharge Coordinator — E2E Test[/]",
                border_style="cyan",
            )
        )

        # Start servers
        for spec in SERVERS:
            console.print(f"Starting [bold]{spec['name']}[/] on :{spec['port']}…")
            proc = start_server(spec, env_extra)
            procs.append(proc)
            time.sleep(0.3)  # stagger starts

        # Wait for all to be healthy
        console.print("\nWaiting for all services to be healthy…")
        for spec in SERVERS:
            ok = wait_healthy(spec["health"], spec["name"])
            status = "[green]✓[/]" if ok else "[red]✗ TIMEOUT[/]"
            console.print(f"  {status} {spec['name']}")
            if not ok:
                console.print(
                    f"[red]ERROR:[/] {spec['name']} failed to start. Check logs."
                )
                sys.exit(1)

        # Send A2A request to orchestrator
        console.print(f"\n[bold]Sending A2A discharge request for {PATIENT}…[/]")
        payload = build_a2a_request(PATIENT, "e2e-demo-token")
        start = time.perf_counter()

        with httpx.Client(timeout=180) as client:
            resp = client.post(
                "http://127.0.0.1:8001/",
                json=payload,
                headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
            )

        duration_s = time.perf_counter() - start
        console.print(
            f"Response in [bold]{duration_s:.1f}s[/] — HTTP {resp.status_code}"
        )

        if resp.status_code != 200:
            console.print(f"[red]ERROR: HTTP {resp.status_code}[/]\n{resp.text[:500]}")
            sys.exit(1)

        data = resp.json()
        text = extract_response_text(data)
        packet = parse_packet(text)
        issues = validate_packet(packet)
        print_summary(packet, duration_s, issues)

        sys.exit(0 if not issues else 1)

    finally:
        console.print("\nShutting down servers…")
        for proc in procs:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
