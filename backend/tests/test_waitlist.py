from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import WaitlistSubscriber


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@patch("app.api.waitlist.send_confirmation_email")
@patch("app.api.waitlist.settings.resend_api_key", "re_test_key")
def test_subscribe_sends_confirmation(mock_send, client):
    mock_send.return_value = None
    response = client.post("/api/waitlist/subscribe", json={"email": "user@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmation_sent"
    assert "inbox" in data["message"].lower()
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "user@example.com"


@patch("app.api.waitlist.send_welcome_email")
@patch("app.api.waitlist.send_confirmation_email")
@patch("app.api.waitlist.settings.resend_api_key", "re_test_key")
def test_confirm_redirects_and_welcomes(mock_confirm, mock_welcome, client):
    mock_confirm.return_value = None
    mock_welcome.return_value = None

    client.post("/api/waitlist/subscribe", json={"email": "confirm@example.com"})

    db = next(app.dependency_overrides[get_db]())
    subscriber = db.query(WaitlistSubscriber).filter_by(email="confirm@example.com").first()
    assert subscriber is not None
    token = subscriber.confirm_token
    db.close()

    response = client.get(f"/api/waitlist/confirm/{token}", follow_redirects=False)
    assert response.status_code == 302
    assert "confirmed=1" in response.headers["location"]
    mock_welcome.assert_called_once_with("confirm@example.com")


@patch("app.api.waitlist.send_confirmation_email")
@patch("app.api.waitlist.settings.resend_api_key", "re_test_key")
def test_already_confirmed(mock_send, client):
    mock_send.return_value = None
    client.post("/api/waitlist/subscribe", json={"email": "done@example.com"})

    db = next(app.dependency_overrides[get_db]())
    subscriber = db.query(WaitlistSubscriber).filter_by(email="done@example.com").first()
    subscriber.confirmed_at = datetime.utcnow()
    subscriber.confirm_token = None
    db.add(subscriber)
    db.commit()
    db.close()

    response = client.post("/api/waitlist/subscribe", json={"email": "done@example.com"})
    assert response.status_code == 200
    assert response.json()["status"] == "already_confirmed"
