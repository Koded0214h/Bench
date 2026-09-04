from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(username="tester", password="pw-tester-123")


@pytest.fixture
def other_user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(username="other", password="pw-other-123")


@pytest.fixture
def auth_api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client
