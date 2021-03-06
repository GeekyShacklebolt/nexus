# Standard Library
import json

# Third Party Stuff
import pytest
from django.urls import reverse

# nexus Stuff
from nexus.users.auth.tokens import get_token_for_password_reset

from .. import factories as f

pytestmark = pytest.mark.django_db


def test_user_registration_with_required_credentials(client):
    url = reverse('auth-register')
    credentials = {
        'email': 'test@test.com',
        'password': 'localhost'
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 201
    expected_keys = [
        'id', 'first_name', 'last_name', 'email', 'gender', 'tshirt_size', 'ticket_id', 'phone_number',
        'is_core_organizer', 'is_volunteer', 'date_joined', 'is_active', 'is_staff', 'is_superuser', 'auth_token'
    ]
    assert set(expected_keys).issubset(response.data.keys())


def test_user_registration_without_required_credentials(client):
    url = reverse('auth-register')
    credentials = {
        'email': 'test@test.com',
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 400
    expected_keys = [
        'errors', 'error_type'
    ]
    assert set(expected_keys).issubset(response.data.keys())
    assert response.data['error_type'] == 'ValidationError'
    assert response.data['errors'][0]['message'] == 'This field is required.'
    assert response.data['errors'][0]['field'] == 'password'


def test_user_registration_with_required_and_other_credentials(client):
    url = reverse('auth-register')
    credentials = {
        'email': 'test@test.com',
        'password': 'localhost',
        'first_name': 'John',
        'last_name': 'Hawley',
        'gender': 'others',
        'tshirt_size': 'extra_extra_large',
        'phone_number': '+911234567890'
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 201
    expected_keys = [
        'id', 'first_name', 'last_name', 'email', 'gender', 'tshirt_size', 'ticket_id', 'phone_number',
        'is_core_organizer', 'is_volunteer', 'date_joined', 'is_active', 'is_staff', 'is_superuser', 'auth_token'
    ]
    assert set(expected_keys).issubset(response.data.keys())
    assert response.data['first_name'] == credentials['first_name']
    assert response.data['last_name'] == credentials['last_name']
    assert response.data['gender'] == credentials['gender']
    assert response.data['tshirt_size'] == credentials['tshirt_size']
    assert response.data['phone_number'] == credentials['phone_number']


def test_user_registration_for_already_registered_email(client):
    url = reverse('auth-register')
    f.create_user(email='test@example.com', password='test')

    credentials = {
        'email': 'test@example.com',
        'password': 'localhost'
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 400
    expected_keys = [
        'errors', 'error_type'
    ]
    assert set(expected_keys).issubset(response.data.keys())
    assert response.data['error_type'] == 'ValidationError'
    assert response.data['errors'][0]['message'] == 'user with this Email Address already exists.'
    assert response.data['errors'][0]['field'] == 'email'


def test_user_login(client):
    url = reverse('auth-login')
    u = f.create_user(email='test@example.com', password='test')

    credentials = {
        'email': u.email,
        'password': 'test'
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 200
    expected_keys = [
        'id', 'first_name', 'last_name', 'email', 'gender', 'tshirt_size', 'ticket_id', 'phone_number',
        'is_core_organizer', 'is_volunteer', 'date_joined', 'is_active', 'is_staff', 'is_superuser', 'auth_token'
    ]
    assert set(expected_keys).issubset(response.data.keys())


def test_user_login_with_incorrect_credentials(client):
    url = reverse('auth-login')
    u = f.create_user(email='test@example.com', password='test')
    credentials = {
        'email': u.email,
        'password': 'wrong_password'
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 400
    expected_keys = [
        'errors', 'error_type'
    ]
    assert set(expected_keys).issubset(response.data.keys())
    assert response.data['error_type'] == 'WrongArguments'
    assert response.data['errors'][0]['message'] == 'Invalid username/password. Please try again!'


def test_user_password_change(client):
    url = reverse('auth-password-change')
    current_password = 'password1'
    new_password = 'paSswOrd2.#$'
    user = f.create_user(email='test@example.com', password=current_password)
    change_password_payload = {
        'current_password': current_password,
        'new_password': new_password
    }

    client.login(user=user)
    response = client.json.post(url, json.dumps(change_password_payload))
    assert response.status_code == 204
    client.logout()

    url = reverse('auth-login')
    credentials = {
        'email': user.email,
        'password': new_password
    }
    response = client.json.post(url, json.dumps(credentials))
    assert response.status_code == 200
    expected_keys = [
        'id', 'first_name', 'last_name', 'email', 'gender', 'tshirt_size', 'ticket_id', 'phone_number',
        'is_core_organizer', 'is_volunteer', 'date_joined', 'is_active', 'is_staff', 'is_superuser', 'auth_token'
    ]
    assert set(expected_keys).issubset(response.data.keys())

    user.refresh_from_db()
    assert user.check_password(new_password)


def test_user_password_reset(client, mailoutbox, settings):
    url = reverse('auth-password-reset')
    user = f.create_user(email='test@example.com')

    response = client.json.post(url, json.dumps({'email': user.email}))
    assert response.status_code == 200
    assert len(mailoutbox) == 1
    mail_body = mailoutbox[0].body
    token = get_token_for_password_reset(user)
    assert "{}://{}".format(settings.FRONTEND_SITE_SCHEME, settings.FRONTEND_SITE_DOMAIN) in mail_body
    assert token in mail_body
    assert user.email in mailoutbox[0].to


def test_user_password_reset_and_confirm(client, settings, mocker):
    url = reverse('auth-password-reset')
    user = f.create_user(email='test@example.com')
    mock_email = mocker.patch('nexus.users.auth.services.send_mail')

    response = client.json.post(url, json.dumps({'email': user.email}))
    assert response.status_code == 200
    assert mock_email.call_count == 1

    args, kwargs = mock_email.call_args
    assert user.email in kwargs.get('recipient_list')

    # get the context passed to template
    token = kwargs['context']['token']

    # confirm we can reset password using context values
    new_password = '$up3r $tr0ng P@$$w0rd'
    password_reset_confirm_data = {
        'new_password': new_password,
        'token': token
    }
    url = reverse('auth-password-reset-confirm')
    response = client.json.post(url, json.dumps(password_reset_confirm_data))
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.check_password(new_password)
