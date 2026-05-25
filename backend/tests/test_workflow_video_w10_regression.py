"""W10 regression bundle: import smoke + fork/reject integration paths."""

from __future__ import annotations

import pytest

import test_workflow_video_w5_rework as w5
import test_workflow_video_w8_events as w8
import test_workflow_video_wfk_fork as wfk


@pytest.mark.asyncio
async def test_w10_wfk_fork_five_topics_still_passes(db_session) -> None:
  await wfk.test_wfk_fork_five_topics_five_child_runs(db_session)


@pytest.mark.asyncio
async def test_w10_w5_capture_reject_still_passes(db_session) -> None:
  await w5.test_w5_reject_topic_reopens_only_submitter(db_session)


@pytest.mark.asyncio
async def test_w10_w8_event_log_still_passes(db_session) -> None:
  await w8.test_w8_capture_reject_persists_event(db_session)
