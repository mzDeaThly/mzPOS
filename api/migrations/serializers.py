from rest_framework import serializers
from .models import (
    Shop, CustomUser, MenuCategory, MenuItem, ShopTable, 
    Order, OrderItem, Subscription, ShopCustomer
)

class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = '__all__'

class MenuCategorySerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'items']

class ShopSerializer(serializers.ModelSerializer):
    categories = MenuCategorySerializer(many=True, read_only=True)
    class Meta:
        model = Shop
        fields = ['id', 'name', 'promptpay_phone', 'promptpay_id_card', 'categories']