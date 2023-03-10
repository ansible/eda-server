from rest_framework import serializers

from aap_eda.core import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ["username", "email", "first_name", "last_name"]
        read_only_fields = ["username"]
