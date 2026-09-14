"""Real PostgreSQL row-lock checks for duplicate worker jobs, retries and receipts."""
import asyncio

import pytest

from app.core.enums import NotificationChannel, NotificationDeliveryStatus, NotificationReceiptType
from app.models import NotificationDelivery, User
from app.services.message_center_service import MessageCenterService
from app.services.notification_service import NotificationService
from app.workers.jobs import process_notification_message_payload
from tests.test_standalone_work_item_postgres_concurrency import postgres_database, pg_session_factory  # noqa: F401
from tests.test_w08_messaging import Queue, seed

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


async def test_concurrent_notification_jobs_receipts_and_retries_apply_once(pg_session_factory):
  async with pg_session_factory() as session:
    _, user, _, queue, _, message = await seed(session, count=1)
    user_id, message_id = user.id, message.id
    push_id = next(d.id for d in message.deliveries if d.channel == NotificationChannel.WEB_PUSH)
    payload = {**queue.payloads[0], 'delivery_ids': [str(push_id)]}
  calls = []
  class Adapter:
    async def send(self, **kwargs):
      calls.append(kwargs['delivery'].id)
      await asyncio.sleep(0.1)
      return 'accepted'
  async def worker():
    async with pg_session_factory() as session:
      await process_notification_message_payload(session=session, payload=payload,
        adapters={NotificationChannel.WEB_PUSH: Adapter()})
  await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(5))), timeout=15)
  assert calls == [push_id]
  async def receipt():
    async with pg_session_factory() as session:
      actor = await session.get(User, user_id)
      row = await MessageCenterService(session).create_receipt(actor=actor, message_id=message_id,
        receipt_type=NotificationReceiptType.READ)
      return row.id
  ids = await asyncio.wait_for(asyncio.gather(*(receipt() for _ in range(5))), timeout=15)
  assert len(set(ids)) == 1
  async with pg_session_factory() as session:
    delivery = await session.get(NotificationDelivery, push_id)
    assert delivery.attempt_count == 1
    delivery.status = NotificationDeliveryStatus.FAILED
    await session.commit()
  retries = Queue()
  async def retry():
    async with pg_session_factory() as session:
      actor = await session.get(User, user_id)
      await NotificationService(session, retries).retry_web_push(actor=actor, message_id=message_id)
  await asyncio.wait_for(asyncio.gather(*(retry() for _ in range(5))), timeout=15)
  assert len(retries.payloads) == 1
  assert retries.payloads[0]['delivery_ids'] == [str(push_id)]
