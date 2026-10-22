import pytest
from accounts.models import Organization, User, Role
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

OLD = "Original-Secure-42!"
NEW = "Updated-Secure-73!"

@pytest.fixture
def user(db):
    org = Organization.objects.create(name="Password test")
    return User.objects.create_user(username="person", email="person@example.test", organization=org, role=Role.REQUESTER, password=OLD)

def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client

def payload(**overrides):
    return {"current_password": OLD, "new_password": NEW, "confirm_password": NEW, **overrides}

@pytest.mark.django_db
def test_requires_authentication(user):
    assert APIClient().post("/api/auth/change-password", payload(), format="json").status_code == 401

@pytest.mark.django_db
@pytest.mark.parametrize("role", Role.values)
def test_every_role_can_change_own_password(user, role):
    user.role = role
    user.save()
    result = client_for(user).post("/api/auth/change-password", payload(), format="json")
    assert result.status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW) and not user.check_password(OLD)
    assert "password" not in result.data

@pytest.mark.django_db
@pytest.mark.parametrize("overrides", [
    {"current_password": "Wrong"},
    {"confirm_password": "Mismatch"},
    {"new_password": "12345678", "confirm_password": "12345678"},
    {"new_password": OLD, "confirm_password": OLD},
    {"new_password": "short", "confirm_password": "short"},
])
def test_invalid_change_preserves_password(user, overrides):
    assert client_for(user).post("/api/auth/change-password", payload(**overrides), format="json").status_code == 400
    user.refresh_from_db()
    assert user.check_password(OLD)

@pytest.mark.django_db
def test_cannot_target_someone_else(user):
    other = User.objects.create_user(username="other", organization=user.organization, role=Role.REQUESTER, password=OLD)
    assert client_for(user).post("/api/auth/change-password", payload(user_id=other.pk), format="json").status_code == 200
    other.refresh_from_db()
    assert other.check_password(OLD)

@pytest.mark.django_db
def test_old_access_and_refresh_revoked(user):
    token = RefreshToken.for_user(user)
    access, refresh = str(token.access_token), str(token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/change-password", payload(), format="json").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert APIClient().post("/api/auth/refresh", {"refresh": refresh}, format="json").status_code == 401
    login = APIClient().post("/api/auth/login", {"username": user.username, "password": NEW}, format="json")
    assert login.status_code == 200
    assert APIClient().post("/api/auth/refresh", {"refresh": login.data["refresh"]}, format="json").status_code == 200

@pytest.mark.django_db
def test_change_password_throttled(user):
    client = client_for(user)
    for _ in range(5):
        assert client.post("/api/auth/change-password", payload(current_password="Wrong"), format="json").status_code == 400
    assert client.post("/api/auth/change-password", payload(), format="json").status_code == 429
