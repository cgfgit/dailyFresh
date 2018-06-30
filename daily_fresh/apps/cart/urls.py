from django.conf.urls import url
from . import views

urlpatterns=[
    url("^add$",views.AddCartView.as_view(),name="add"),
    url("^info$",views.CartInfoView.as_view(),name="info"),
    url("^update$",views.UpdateCartView.as_view(),name="update"),
    url("^delete$",views.DeleteCartView.as_view(),name="delete"),
    
    
    ]