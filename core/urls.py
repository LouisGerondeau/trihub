# core/urls.py
from django.conf import settings
from django.urls import include, path

from . import views

urlpatterns = [
    path("public/<slug:category_code>/", views.public_sessions, name="public_sessions"),
    path(
        "public/<slug:category_code>/<int:session_id>/unassign/<int:coach_id>/",
        views.unassign_confirm,
        name="unassign_confirm",
    ),
    path(
        "public/<slug:category_code>/<int:session_id>/unassign/<int:coach_id>/confirm/",
        views.unassign_do,
        name="unassign_do",
    ),
    path(
        "public/<slug:category_code>/<int:session_id>/assign/",
        views.assign_confirm,
        name="assign_confirm",
    ),
    path(
        "public/<slug:category_code>/<int:session_id>/assign/confirm/",
        views.assign_do,
        name="assign_do",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
