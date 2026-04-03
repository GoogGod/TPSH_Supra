from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.views.generic import View


class FrontendAppView(View):
    """
    Serve compiled SPA entrypoint.
    If frontend build is missing, return a helpful message instead of 500.
    """

    def get(self, request, *args, **kwargs):
        try:
            template = get_template("index.html")
        except TemplateDoesNotExist:
            return HttpResponse(
                "Frontend build not found. Build `front/` and deploy again.",
                status=503,
            )
        return HttpResponse(template.render({}, request))
