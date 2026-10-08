from django.urls import path, include
from django.urls import re_path
from social_django import views as django_social_views

from . import views, social_accounts_views

social_patterns = [
    # authentication / association
    re_path(r"^login/(?P<backend>[^/]+)/$", django_social_views.auth, name="begin"),
    re_path(r"^complete/(?P<backend>[^/]+)/$", views.complete, name="complete"),
    # No disconnection route: social_django's stock disconnect view requires only an
    # authenticated session (no fresh password/OTP/passkey proof), the same gap this
    # app closes for OTP management and passkey management elsewhere. Add an unlink
    # flow here only once it's gated by the same fresh-auth pattern as those.
]

user_patterns = [
    path("social-accounts/", social_accounts_views.SocialAccountsView.as_view(), name="social_accounts"),
    path("social-accounts/unlink/options/", social_accounts_views.SocialUnlinkOptionsView.as_view()),
    path("social-accounts/unlink/", social_accounts_views.SocialUnlinkView.as_view()),
    path('social-link/cancel/', views.CancelSocialLinkView.as_view(), name='cancel_social_link'),
    path("token-refresh/", views.CookieTokenRefreshView.as_view(), name="jwt_token_refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("social/", include((social_patterns, "social"), namespace="social")),
]

urlpatterns = [path("auth/", include(user_patterns))]
