import json
import os
import subprocess
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app.scraper.gosom import GosomScraperAdapter
from app.scraper.schemas import ReviewScrapeResult

def test_gosom_not_available_by_default():
    adapter = GosomScraperAdapter(binary_path="/nonexistent/path/to/google-maps-scraper")
    assert adapter.is_available() is False

@pytest.mark.asyncio
async def test_gosom_returns_no_data_when_binary_missing():
    adapter = GosomScraperAdapter(binary_path="/nonexistent/path/to/google-maps-scraper")
    res = await adapter.scrape_reviews("https://maps.google.com/test")
    assert res.status == "NO_DATA"
    assert "not installed" in res.error_message

@pytest.mark.asyncio
async def test_gosom_parses_real_gosom_json_output():
    # Mock real gosom output structure with user_reviews_extended and user_reviews
    mock_gosom_output = [
        {
            "title": "Downtown Bistro",
            "category": "Restaurant",
            "address": "123 Main St",
            "review_count": 150,
            "review_rating": 4.2,
            "user_reviews": [
                {
                    "name": "Sarah Connor",
                    "rating": 5,
                    "relative_date": "3 weeks ago",
                    "text": "Incredible ambiance and pasta dishes!"
                }
            ],
            "user_reviews_extended": [
                {
                    "name": "Kyle Reese",
                    "rating": 2,
                    "relative_date": "a month ago",
                    "text": "Waited 50 minutes for a table on Saturday night.",
                    "response": "We apologize for the delay during rush hour.",
                    "response_date": "3 weeks ago"
                }
            ]
        }
    ]

    adapter = GosomScraperAdapter(binary_path="fake_gosom_bin")

    with patch.object(adapter, "is_available", return_value=True):
        def fake_run(cmd, capture_output, text, timeout):
            # Write mock output to the -results path specified in cmd
            results_idx = cmd.index("-results") + 1
            results_path = cmd[results_idx]
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(mock_gosom_output, f)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_run) as mock_subproc:
            res = await adapter.scrape_reviews("https://maps.google.com/place/123", depth=1)

            assert mock_subproc.called
            cmd = mock_subproc.call_args[0][0]
            assert "-input" in cmd
            assert "-results" in cmd
            assert "-json" in cmd
            assert "-extra-reviews" in cmd

            assert res.status == "SUCCESS"
            assert len(res.reviews) == 2

            # Check Sarah's review from user_reviews
            sarah = next(r for r in res.reviews if r.author_name == "Sarah Connor")
            assert sarah.rating == 5.0
            assert sarah.text == "Incredible ambiance and pasta dishes!"
            assert sarah.relative_time_description == "3 weeks ago"
            assert sarah.source == "gosom_scraper"
            assert sarah.fingerprint is not None

            # Check Kyle's review from user_reviews_extended
            kyle = next(r for r in res.reviews if r.author_name == "Kyle Reese")
            assert kyle.rating == 2.0
            assert "Waited 50 minutes" in kyle.text
            assert kyle.response_text == "We apologize for the delay during rush hour."
            assert kyle.source == "gosom_scraper"

@pytest.mark.asyncio
async def test_gosom_handles_timeout():
    adapter = GosomScraperAdapter(binary_path="fake_gosom_bin")

    with patch.object(adapter, "is_available", return_value=True):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["gosom"], timeout=120)):
            res = await adapter.scrape_reviews("https://maps.google.com/test")
            assert res.status == "ERROR"
            assert "timed out" in res.error_message.lower()

@pytest.mark.asyncio
async def test_gosom_handles_process_failure():
    adapter = GosomScraperAdapter(binary_path="fake_gosom_bin")

    with patch.object(adapter, "is_available", return_value=True):
        fake_proc = subprocess.CompletedProcess(args=["gosom"], returncode=1, stdout="", stderr="Crash error")
        with patch("subprocess.run", return_value=fake_proc):
            res = await adapter.scrape_reviews("https://maps.google.com/test")
            assert res.status == "ERROR"
            assert "exited with code 1" in res.error_message

