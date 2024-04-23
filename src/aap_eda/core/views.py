from django.db import connection
from django.db.utils import OperationalError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connection.ensure_connection()
            return Response({"status": "OK"}, status=200)
        except OperationalError:
            return Response(
                {"status": "error", "message": "Database connection failed"},
                status=500,
            )


class StatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connection.ensure_connection()
            return Response({"status": "OK"}, status=200)
        except OperationalError:
            return Response(
                {"status": "error", "message": "Database connection failed"},
                status=500,
            )
