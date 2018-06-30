from django.conf.urls import url
from . import views

urlpatterns=[
    url("^place$",views.PlaceOrderView.as_view(),name="place"),
    url("^commit$",views.CommitOrderView.as_view(),name="commit"),
    url("^info/(?P<page>\d+)$",views.UserOrderView.as_view(),name="info"),
    ]