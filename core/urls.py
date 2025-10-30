# core/urls.py
from django.conf import settings
from django.urls import include, path

from . import views

urlpatterns = [
    path(
        "public/category/<slug:category_code>/",
        views.public_sessions_by_category,
        name="public_sessions_by_category",
    ),
    path(
        "public/unassign/confirm/",
        views.unassign_confirm,
        name="unassign_confirm",
    ),
    path(
        "public/unassign/do/",
        views.unassign_do,
        name="unassign_do",
    ),
    path(
        "public/assign/confirm/",
        views.assign_confirm,
        name="assign_confirm",
    ),
    path(
        "public/assign/do/",
        views.assign_do,
        name="assign_do",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
