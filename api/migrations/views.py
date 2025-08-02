from rest_framework import viewsets
from .models import Shop, MenuCategory, MenuItem
from .serializers import ShopSerializer, MenuCategorySerializer, MenuItemSerializer

class ShopViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing Shops and their nested menus.
    """
    queryset = Shop.objects.prefetch_related('categories__items').all()
    serializer_class = ShopSerializer

class MenuCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Menu Categories.
    """
    queryset = MenuCategory.objects.all()
    serializer_class = MenuCategorySerializer

class MenuItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Menu Items.
    """
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer