from django.urls import include, path

from fuel_optimizer import views

urlpatterns = [
    path("api/v1/", include("fuel_optimizer.urls")),
    path("demo/", views.demo, name="demo"),
    path("docs/", views.docs, name="docs"),
    path("openapi.json", views.openapi, name="openapi"),
    path("", views.demo),
]
