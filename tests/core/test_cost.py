"""Tests for CostTracker."""
import pytest
from opencode.core.cost import CostTracker
from opencode.core.message import Usage


class TestCostTracker:
    def test_initial_state(self):
        ct = CostTracker()
        assert ct.total_input_tokens == 0
        assert ct.total_output_tokens == 0
        assert ct.total_requests == 0

    def test_record_single(self):
        ct = CostTracker()
        ct.record(Usage(input_tokens=100, output_tokens=50, total_tokens=150))
        assert ct.total_input_tokens == 100
        assert ct.total_output_tokens == 50
        assert ct.total_requests == 1

    def test_record_multiple_accumulates(self):
        ct = CostTracker()
        ct.record(Usage(input_tokens=100, output_tokens=50, total_tokens=150))
        ct.record(Usage(input_tokens=200, output_tokens=75, total_tokens=275))
        assert ct.total_input_tokens == 300
        assert ct.total_output_tokens == 125
        assert ct.total_requests == 2

    def test_record_zero_usage(self):
        ct = CostTracker()
        ct.record(Usage())
        assert ct.total_input_tokens == 0
        assert ct.total_output_tokens == 0
        assert ct.total_requests == 1

    def test_summary_format(self):
        ct = CostTracker()
        ct.record(Usage(input_tokens=1000, output_tokens=500, total_tokens=1500))
        summary = ct.summary()
        assert "1,500" in summary
        assert "1,000" in summary
        assert "500" in summary
        assert "1 request" in summary

    def test_summary_multiple_requests(self):
        ct = CostTracker()
        ct.record(Usage(input_tokens=500, output_tokens=250))
        ct.record(Usage(input_tokens=500, output_tokens=250))
        summary = ct.summary()
        assert "2 requests" in summary
        assert "1,500" in summary  # 500+250+500+250 = 1500 total

    def test_summary_zero_requests(self):
        ct = CostTracker()
        summary = ct.summary()
        assert "0" in summary
        assert "requests" in summary
