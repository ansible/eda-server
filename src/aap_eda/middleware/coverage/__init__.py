import coverage


class CoverageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.cov = coverage.Coverage()

    def __call__(self, request):
        self.cov.start()
        response = self.get_response(request)
        self.cov.stop()
        self.cov.save()

        return response
