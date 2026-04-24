from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from apps.merchants.models import Merchant
from apps.merchants.serializers import MerchantSerializer, RegisterSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = serializer.save()
        return Response(
            MerchantSerializer(merchant).data,
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    def get(self, request):
        merchant = request.user.merchant
        return Response(MerchantSerializer(merchant).data)

    def patch(self, request):
        merchant = request.user.merchant
        serializer = MerchantSerializer(merchant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
