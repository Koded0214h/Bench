from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def auth_api(db) -> APIClient:
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create(username="tester", is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client
