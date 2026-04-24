from rest_framework import serializers
from django.contrib.auth.models import User
from apps.merchants.models import Merchant


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


class MerchantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    balance_paise = serializers.SerializerMethodField()
    balance_inr = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = [
            "id", "business_name", "webhook_url",
            "balance_paise", "balance_inr", "created_at", "user",
        ]
        read_only_fields = ["id", "created_at"]

    def get_balance_paise(self, obj) -> int:
        return obj.get_balance()

    def get_balance_inr(self, obj) -> str:
        paise = obj.get_balance()
        return f"₹{paise / 100:.2f}"


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField()
    business_name = serializers.CharField(max_length=255)
    webhook_url = serializers.URLField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def create(self, validated_data):
        webhook_url = validated_data.pop("webhook_url", None)
        business_name = validated_data.pop("business_name")
        user = User.objects.create_user(**validated_data)
        merchant = Merchant.objects.create(
            user=user,
            business_name=business_name,
            webhook_url=webhook_url,
        )
        return merchant
