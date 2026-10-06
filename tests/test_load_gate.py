"""Exercise the actual JTL gate, including failure paths and exact boundaries."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "load-tests" / "check_results.py"
SPEC = importlib.util.spec_from_file_location("load_gate", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def write_results(tmp_path, durations, failures=0):
    path = tmp_path / "results.jtl"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timeStamp", "elapsed", "label", "success"])
        for index, elapsed in enumerate(durations):
            writer.writerow([1000 + index * 10, elapsed, "GET summary", index >= failures])
    return path


def test_exact_error_and_latency_boundaries_pass(tmp_path, capsys):
    path = write_results(tmp_path, [1000] * 100, failures=1)
    assert gate.main([str(path), "--max-error-rate", "0.01", "--p95-ms", "1000"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["passed"] is True
    assert result["errors"] == 1
    assert result["error_rate"] == 0.01
    assert result["throughput_rps"] == round(100 / 1.99, 3)


@pytest.mark.parametrize("failures,durations", [(2, [100] * 100), (0, [1001] * 100)])
def test_threshold_violations_fail(tmp_path, failures, durations, capsys):
    path = write_results(tmp_path, durations, failures)
    assert gate.main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["violations"]


def test_nearest_rank_percentiles_include_tail():
    assert gate.percentile(list(range(1, 101)), 0.95) == 95
    assert gate.percentile([5, 999], 0.95) == 999


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "timeStamp,elapsed,label,success\n",
        "timeStamp,elapsed,label\n1000,10,GET\n",
        "timeStamp,elapsed,label,success\n1000,-10,GET,true\n",
        "timeStamp,elapsed,label,success\n1000,10,GET,unknown\n",
        "timeStamp,elapsed,label,success\n1000,10,GET\n",
        "timeStamp,elapsed,label,success\n1000,10,GET,true,extra\n",
        "timeStamp,elapsed,label,success\nNaN,10,GET,true\n",
        "timeStamp,elapsed,label,success\n1000,0,GET,true\n",
    ],
)
def test_empty_or_malformed_results_fail_closed(tmp_path, contents, capsys):
    path = tmp_path / "invalid.jtl"
    path.write_text(contents, encoding="utf-8")
    assert gate.main([str(path)]) == 2
    assert "invalid_results" in json.loads(capsys.readouterr().err)


def test_missing_file_fails_closed(tmp_path):
    assert gate.main([str(tmp_path / "missing.jtl")]) == 2


@pytest.mark.parametrize("args", [["--max-error-rate", "nan"], ["--p95-ms", "inf"]])
def test_invalid_thresholds_are_rejected(tmp_path, args):
    with pytest.raises(SystemExit) as error:
        gate.main([str(tmp_path / "unused.jtl"), *args])
    assert error.value.code == 2
