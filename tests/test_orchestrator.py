"""Unit tests for orchestrator helpers."""
import pytest
import json
from agents.orchestrator.tools import _extract_text_from_a2a_response, _parse_json_response


def test_extract_text_from_artifacts():
    response = {
        "result": {
            "artifacts": [
                {"parts": [{"kind": "text", "text": '{"status": "success"}'}]}
            ]
        }
    }
    text = _extract_text_from_a2a_response(response)
    assert text == '{"status": "success"}'


def test_extract_text_from_status():
    response = {
        "result": {
            "status": {
                "message": {
                    "parts": [{"kind": "text", "text": '{"status": "success"}'}]
                }
            }
        }
    }
    text = _extract_text_from_a2a_response(response)
    assert text == '{"status": "success"}'


def test_parse_json_clean():
    data = _parse_json_response('{"status": "success", "patient_id": "patient-001"}')
    assert data["status"] == "success"


def test_parse_json_markdown_fenced():
    text = '```json\n{"status": "success"}\n```'
    data = _parse_json_response(text)
    assert data["status"] == "success"


def test_parse_json_bad_falls_back():
    data = _parse_json_response("not json at all")
    assert data["status"] == "parse_error"
