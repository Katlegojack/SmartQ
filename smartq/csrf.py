from django.http import JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure


def csrf_failure(request, reason=""):
    """Return a machine-readable CSRF failure for Smart Q API requests.

    Django's middleware rejects an invalid token before DRF can format a JSON
    response. Browser clients need a stable signal so they can fetch a fresh
    token and retry automatically instead of rendering Django's HTML 403 page.
    Non-API requests keep Django's normal failure view.
    """

    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "detail": "Smart Q secure-session verification failed.",
                "csrfFailure": True,
            },
            status=403,
        )

    return django_csrf_failure(request, reason=reason)
