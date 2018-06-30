from django.conf.urls import url
from . import views
urlpatterns=[
    url("^register$", views.RegisterView.as_view(),name="register"),
    url("^active/(?P<token>.+)$", views.ActiveView.as_view(),name="active"),
    url("^login$", views.LoginView.as_view(),name="login"),
    url("^logout$",views.LogoutView.as_view(),name="logout"),
    url("^address$",views.UserAddressView.as_view(),name="address"),
    url("^info$",views.UserInfoView.as_view(),name="info"),
    ]