#!/usr/bin/env python3
"""
Simulates exactly how the Prompt Opinion platform calls our agents.

Demonstrates:
  1. Discovery — fetching the agent card from /.well-known/agent-card.json
  2. A2A SendMessage — calling the orchestrator with SHARP fhir-context metadata
  3. Response parsing — extracting the discharge packet from the A2A result

This lets us validate platform integration BEFORE submitting to Prompt Opinion.

Usage:
    # Assumes all agents are already running (use make run-agents in separate terminal)
    uv run python scripts/simulate_promptopinion.py [patient-001|patient-002|patient-003]

DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.
"""

import json
import os
import sys
import uuid
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

load_dotenv()
console = Console()

PATIENT = sys.argv[1] if len(sys.argv) > 1 else "patient-001"
API_KEY = os.getenv("AGENT_API_KEY", "demo-key-e2e")
FHIR_URL = os.getenv("FHIR_BASE_URL", "http://localhost:8000/fhir")
ORCH_URL = f"http://localhost:{os.getenv('ORCHESTRATOR_PORT', '8001')}"
FHIR_EXT = os.getenv(
    "FHIR_EXTENSION_URI", "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context"
)


def step(n: int, title: str):
    console.rule(f"[bold cyan]Step {n}: {title}[/]")


def main():
    console.print(
        Panel(
            "[bold]Prompt Opinion Platform Simulation[/]\n"
            f"Agent under test: Discharge Coordinator (Orchestrator)\n"
            f"Patient: [bold]{PATIENT}[/]\n"
            "[dim]DEMO ONLY — SYNTHETIC DATA. NOT FOR CLINICAL USE.[/dim]",
            border_style="cyan",
        )
    )

    # ── Step 1: Discover agent card ────────────────────────────────────────────
    step(1, "Agent Discovery — fetch /.well-known/agent-card.json")
    card_url = f"{ORCH_URL}/.well-known/agent-card.json"
    console.print(f"GET {card_url}")

    try:
        r = httpx.get(card_url, timeout=10)
        r.raise_for_status()
        card = r.json()
        console.print(f"[green]✓ Agent card fetched (HTTP {r.status_code})[/]")
        console.print(f"  name:    {card.get('name', '?')}")
        console.print(f"  version: {card.get('version', '?')}")

        # Show declared FHIR extension
        caps = card.get("capabilities", {})
        extensions = caps.get("extensions", [])
        for ext in extensions:
            if "fhir" in ext.get("uri", "").lower():
                console.print(f"  [green]✓ FHIR extension declared:[/] {ext['uri']}")
                scopes = (ext.get("params") or {}).get("scopes", [])
                for s in scopes:
                    req = "required" if s.get("required") else "optional"
                    console.print(f"      scope: {s['name']} ({req})")

        # Show skills
        for skill in card.get("skills", []):
            console.print(
                f"  skill: [bold]{skill.get('name')}[/] — {skill.get('description', '')[:80]}"
            )

    except Exception as e:
        console.print(f"[red]✗ Agent card fetch failed: {e}[/]")
        console.print("  Is the orchestrator running? Try: make run-agents")
        sys.exit(1)

    console.print()

    # ── Step 2: Build A2A SendMessage request ──────────────────────────────────
    step(2, "Build A2A SendMessage request with FHIR context metadata")

    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": f"Prepare discharge packet for patient {PATIENT}.",
                    }
                ],
                "metadata": {
                    FHIR_EXT: {
                        "fhirUrl": FHIR_URL,
                        "fhirToken": "po-demo-bearer-token",
                        "patientId": PATIENT,
                    }
                },
            }
        },
    }

    console.print(
        Syntax(json.dumps(payload, indent=2)[:600] + "\n  ...", "json", theme="monokai")
    )

    # ── Step 3: Send request ───────────────────────────────────────────────────
    step(3, f"POST to {ORCH_URL}/ (A2A JSON-RPC endpoint)")
    console.print(f"[dim]Headers: X-API-Key: {API_KEY[:4]}...[/dim]")

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=180) as client:
            resp = client.post(
                f"{ORCH_URL}/",
                json=payload,
                headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
            )
    except httpx.TimeoutException:
        console.print("[red]✗ Request timed out after 180s[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Request failed: {e}[/]")
        sys.exit(1)

    elapsed = time.perf_counter() - start
    console.print(
        f"[green]✓ Response received in {elapsed:.1f}s (HTTP {resp.status_code})[/]"
    )

    if resp.status_code != 200:
        console.print(f"[red]ERROR: {resp.text[:500]}[/]")
        sys.exit(1)

    # ── Step 4: Parse response ────────────────────────────────────────────────
    step(4, "Parse A2A response — extract discharge packet")

    data = resp.json()
    result = data.get("result", {})
    artifacts = result.get("artifacts", [])
    text = ""
    if artifacts:
        parts = artifacts[0].get("parts", [])
        if parts:
            text = parts[0].get("text", "")
    if not text:
        status = result.get("status", {})
        msg = status.get("message", {})
        parts = msg.get("parts", [])
        if parts:
            text = parts[0].get("text", "")

    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        packet = json.loads(text)
    except Exception:
        console.print(
            f"[yellow]Note: Response is not JSON. Raw text:[/]\n{text[:1000]}"
        )
        sys.exit(0)

    # ── Step 5: Show results ──────────────────────────────────────────────────
    step(5, "Discharge Packet Summary")

    patient_name = packet.get("patient_name", packet.get("patient_id", "?"))
    console.print(f"[bold]Patient:[/] {patient_name}")
    console.print(
        f"[bold]Duration:[/] {packet.get('total_duration_ms', '?')}ms (agent-reported)"
    )

    for section, label in [
        ("medications", "MedRecon"),
        ("care_instructions", "CarePlan"),
        ("follow_up", "FollowUp"),
    ]:
        s = packet.get(section, {})
        status_str = s.get("status", "missing")
        color = "green" if status_str == "success" else "red"
        console.print(
            f"  [{color}]{'✓' if status_str == 'success' else '✗'}[/{color}] {label}: {status_str}"
        )

    prov_count = len(packet.get("provenance", []))
    console.print(f"\n[bold]Provenance citations:[/] {prov_count} FHIR resources cited")
    console.print(f"[bold]Disclaimer:[/] {packet.get('disclaimer', '[MISSING]')}")

    # Save full packet for inspection
    out_path = Path(__file__).parent.parent / f"discharge_packet_{PATIENT}.json"
    out_path.write_text(json.dumps(packet, indent=2))
    console.print(f"\n[dim]Full packet saved to {out_path.name}[/]")

    console.rule("[bold green]Simulation complete[/]")


if __name__ == "__main__":
    main()
