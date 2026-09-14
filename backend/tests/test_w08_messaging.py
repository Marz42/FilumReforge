from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.routes.push_subscriptions import send_test_push_notification
from app.core.config import Settings
from app.core.enums import NotificationChannel as Channel, NotificationDeliveryStatus as DeliveryStatus
from app.core.enums import NotificationReceiptType, PushSubscriptionStatus
from app.core.enums import UserRole
from app.core.exceptions import ConflictError, ConfigurationError, NotFoundError
from app.integrations.notifications.web_push import WebPushNotificationAdapter
from app.models import NotificationReceipt
from app.schemas.messages import NotificationMessage
from app.services.auth_service import AuthService
from app.services.browser_push_service import BrowserPushService
from app.services.message_center_service import MessageCenterService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from app.workers.jobs import process_notification_message_payload


class Queue:
  def __init__(self, fail=False):
    self.payloads = []
    self.fail = fail

  async def publish(self, payload):
    if self.fail:
      raise RuntimeError('secret-provider-endpoint')
    self.payloads.append(payload)


async def seed(session, count=2):
  settings = Settings(web_push_public_key='public', web_push_private_key='private',
                      web_push_subject='mailto:test@example.com')
  user = await AuthService(session, settings).bootstrap_admin(
    email='w08@example.com', password='StrongPassword123!', real_name='W08', employee_no='W08')
  push = BrowserPushService(session)
  subscriptions = [await push.upsert_subscription(actor=user, endpoint=f'https://push.example.test/{i}',
                   p256dh_key='key', auth_key='auth', user_agent='test') for i in range(count)]
  queue = Queue()
  service = NotificationService(session, queue)
  message = await service.send(NotificationMessage(source_type='system', recipient_user_id=user.id,
    message_type='test', title='W08', body_text='message', channels=[Channel.WEB_PUSH, Channel.EMAIL]))
  return settings, user, subscriptions, queue, service, message


@pytest.mark.asyncio
@pytest.mark.parametrize('status_code', [404, 410, 503])
async def test_partial_push_is_accepted_with_warning_and_not_repeated(db_session, status_code):
  settings, user, subscriptions, queue, service, message = await seed(db_session)
  calls = []
  def sender(**kwargs):
    endpoint = kwargs['subscription_info']['endpoint']
    calls.append(endpoint)
    if endpoint.endswith('/0'):
      error = RuntimeError('secret-provider-endpoint')
      error.status_code = status_code
      raise error
  adapter = WebPushNotificationAdapter(session=db_session, settings=settings, sender=sender)
  payload = {**queue.payloads[0], 'delivery_ids': [str(d.id) for d in message.deliveries if d.channel == Channel.WEB_PUSH]}
  await process_notification_message_payload(session=db_session, payload=payload, adapters={Channel.WEB_PUSH: adapter})
  delivery = next(d for d in message.deliveries if d.channel == Channel.WEB_PUSH)
  assert delivery.status == DeliveryStatus.SENT
  assert '1/2' in delivery.error_message
  assert 'secret-provider' not in delivery.error_message
  assert subscriptions[0].status == (PushSubscriptionStatus.EXPIRED if status_code in {404, 410} else PushSubscriptionStatus.ACTIVE)
  await process_notification_message_payload(session=db_session, payload=payload, adapters={Channel.WEB_PUSH: adapter})
  await service.retry_web_push(actor=user, message_id=message.id)
  assert len(calls) == 2
  assert len(queue.payloads) == 1
  assert not list(await db_session.scalars(select(NotificationReceipt)))


@pytest.mark.asyncio
async def test_failed_push_retry_is_scoped_bounded_and_recipient_only(db_session):
  settings, user, _, queue, service, message = await seed(db_session)
  def sender(**kwargs):
    raise OSError('secret-provider-endpoint')
  push = next(d for d in message.deliveries if d.channel == Channel.WEB_PUSH)
  email = next(d for d in message.deliveries if d.channel == Channel.EMAIL)
  email.status = DeliveryStatus.SENT
  await db_session.commit()
  await process_notification_message_payload(session=db_session, payload=queue.payloads[0],
    adapters={Channel.WEB_PUSH: WebPushNotificationAdapter(session=db_session, settings=settings, sender=sender)})
  assert push.status == DeliveryStatus.FAILED
  assert '0/2' in push.error_message and 'secret-provider' not in push.error_message
  with pytest.raises(NotFoundError):
    await service.retry_web_push(actor=user, message_id=uuid4())
  await service.retry_web_push(actor=user, message_id=message.id)
  assert queue.payloads[-1]['delivery_ids'] == [str(push.id)]
  assert push.status == DeliveryStatus.RETRYING
  await service.retry_web_push(actor=user, message_id=message.id)
  assert len(queue.payloads) == 2
  push.status, push.attempt_count = DeliveryStatus.FAILED, 5
  await db_session.commit()
  with pytest.raises(ConflictError):
    await service.retry_web_push(actor=user, message_id=message.id)
  assert email.status == DeliveryStatus.SENT


@pytest.mark.asyncio
async def test_retry_queue_failure_preserves_success_and_sanitizes_error(db_session):
  _, user, _, _, _, message = await seed(db_session)
  push = next(d for d in message.deliveries if d.channel == Channel.WEB_PUSH)
  email = next(d for d in message.deliveries if d.channel == Channel.EMAIL)
  push.status, email.status = DeliveryStatus.FAILED, DeliveryStatus.SENT
  await db_session.commit()
  with pytest.raises(ConfigurationError):
    await NotificationService(db_session).retry_web_push(actor=user, message_id=message.id)
  await NotificationService(db_session, Queue(fail=True)).retry_web_push(actor=user, message_id=message.id)
  assert push.status == DeliveryStatus.FAILED
  assert 'secret-provider' not in push.error_message
  assert email.status == DeliveryStatus.SENT and email.attempt_count == 0


@pytest.mark.asyncio
async def test_other_recipient_cannot_read_retry_receipt_or_revoke(db_session):
  _, owner, subscriptions, _, service, message = await seed(db_session)
  other = await UserService(db_session).create_user(actor=owner, email='other@example.com',
    password='StrongPassword123!', role=UserRole.EMPLOYEE)
  center = MessageCenterService(db_session)
  assert (await center.get_message_center_snapshot(actor=other)).total_count == 0
  with pytest.raises(NotFoundError):
    await center.get_message_view(actor=other, message_id=message.id)
  with pytest.raises(NotFoundError):
    await center.create_receipt(actor=other, message_id=message.id, receipt_type=NotificationReceiptType.READ)
  with pytest.raises(NotFoundError):
    await service.retry_web_push(actor=other, message_id=message.id)
  with pytest.raises(NotFoundError):
    await BrowserPushService(db_session).revoke_subscription(actor=other, subscription_id=subscriptions[0].id)


@pytest.mark.asyncio
async def test_channel_filter_uses_same_delivery_and_receipts_ignore_push_failure(db_session):
  _, user, _, _, _, message = await seed(db_session)
  for delivery in message.deliveries:
    delivery.status = DeliveryStatus.SENT if delivery.channel == Channel.WEB_PUSH else DeliveryStatus.FAILED
  await db_session.commit()
  center = MessageCenterService(db_session)
  snapshot = await center.get_message_center_snapshot(actor=user, channel=Channel.WEB_PUSH,
    delivery_status=DeliveryStatus.SENT, created_from=datetime.now(UTC)-timedelta(days=1))
  assert snapshot.filtered_count == 1 and snapshot.unread_count == 1
  assert (await center.get_message_center_snapshot(actor=user, channel=Channel.WEB_PUSH,
    delivery_status=DeliveryStatus.FAILED)).filtered_count == 0
  first = await center.create_receipt(actor=user, message_id=message.id, receipt_type=NotificationReceiptType.ACKNOWLEDGED)
  again = await center.create_receipt(actor=user, message_id=message.id, receipt_type=NotificationReceiptType.ACKNOWLEDGED)
  assert first.id == again.id
  snapshot = await center.get_message_center_snapshot(actor=user)
  assert snapshot.unread_count == snapshot.unacknowledged_count == 0


@pytest.mark.asyncio
async def test_test_push_reports_queue_failure_and_rejects_disabled_configuration(db_session):
  settings, user, subscriptions, _, _, message = await seed(db_session)
  push_service = BrowserPushService(db_session)
  service = NotificationService(db_session, Queue(fail=True))
  result = await send_test_push_notification(user, push_service, service, settings)
  assert result.status.value == 'failed' and '入队失败' in result.detail
  with pytest.raises(ConflictError):
    await send_test_push_notification(user, push_service, service, Settings(web_push_private_key=''))
  for subscription in subscriptions:
    subscription.status = PushSubscriptionStatus.REVOKED
  delivery = next(d for d in message.deliveries if d.channel == Channel.WEB_PUSH)
  delivery.status = DeliveryStatus.FAILED
  await db_session.commit()
  with pytest.raises(ConflictError):
    await service.retry_web_push(actor=user, message_id=message.id)
