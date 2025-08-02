from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShopViewSet, MenuCategoryViewSet, MenuItemViewSet

router = DefaultRouter()
router.register(r'shops', ShopViewSet, basename='shop')
router.register(r'categories', MenuCategoryViewSet, basename='menucategory')
router.register(r'menu-items', MenuItemViewSet, basename='menuitem')

urlpatterns = [
    path('', include(router.urls)),
]