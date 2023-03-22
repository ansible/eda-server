# Not implemented in the api yet
# flake8: noqa
# import eda_api.apis as apis
# from eda_qa.api.common import BaseApi
# class UsersApi(BaseApi):
#     """
#     Wraps the openapi api for users endpoints
#     """
#     api = apis.UsersApi
# class CurrentUserApi(UsersApi):
#     """
#     Wraps the openapi api for current user endpoints
#     """
#     def read(self):
#         operation = "users_current_user_api_users_me_get"
#         return self.run(operation)
# class AuthApi(BaseApi):
#     """
#     Wraps the openapi api for auth endpoints
#     """
#     api = apis.AuthApi
#     def login(self, username, password):
#         operation = "auth_bearer_login_api_auth_bearer_login_post"
#         return self.run(operation, username=username, password=password)
