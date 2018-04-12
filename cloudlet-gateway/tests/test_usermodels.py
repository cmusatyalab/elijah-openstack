# project/tests/test_user_model.py


import pytest
import context

from caas.provider.models import Role, User

@pytest.mark.usefixtures('db')
class TestUserModel:
    def test_encode_auth_token(self):
        user = User(username='test_user_model', email='test_user_model@test.com', password='test_user_model_pw',
                    active=True)
        user.save()
        auth_token = user.encode_auth_token(user.id)
        assert isinstance(auth_token, bytes)

    def test_decode_auth_token(self):
        user = User(username='test_user_model', email='test_user_model@test.com', password='test_user_model_pw',
                    active=True)
        user.save()
        auth_token = user.encode_auth_token(user.id)
        assert isinstance(auth_token, bytes)
        assert User.decode_auth_token(auth_token) == 1
