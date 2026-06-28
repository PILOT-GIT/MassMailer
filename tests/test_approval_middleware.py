import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot.middlewares import ApprovalMiddleware
from config import settings
from models import User


class DummyResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class DummySession:
    def __init__(self, user):
        self.user = user
        self.added = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        return DummyResult(self.user)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        return None


class DummyEvent:
    def __init__(self, user_id, username):
        self.from_user = SimpleNamespace(id=user_id, username=username)


class ApprovalMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_with_existing_unapproved_record_is_auto_approved(self):
        existing_user = User(
            telegram_id=settings.ADMIN_TELEGRAM_ID,
            telegram_username="admin",
            is_approved=False,
        )
        session = DummySession(existing_user)

        class DummySessionContext:
            def __init__(self, session):
                self.session = session

            async def __aenter__(self):
                return self.session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        async def handler(event, data):
            self.assertTrue(data["db_user"].is_approved)
            return "ok"

        with patch("bot.middlewares.AsyncSessionLocal", lambda: DummySessionContext(session)):
            result = await ApprovalMiddleware()(handler, DummyEvent(settings.ADMIN_TELEGRAM_ID, "admin"), {})

        self.assertEqual(result, "ok")
        self.assertTrue(existing_user.is_approved)


if __name__ == "__main__":
    unittest.main()
