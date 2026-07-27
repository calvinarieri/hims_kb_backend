from django.contrib import admin
from .models import Role, User, Product, ProductVersion


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'role')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    # Organizes fields cleanly on the edit page
    fieldsets = (
        ('Account Credentials', {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at')


class ProductVersionInline(admin.TabularInline):
    """Allows managing Product Versions directly inside the Product admin view."""
    model = ProductVersion
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'api_key', 'created_at', 'updated_at')
    search_fields = ('name', 'api_key')
    ordering = ('-created_at',)
    inlines = [ProductVersionInline]


@admin.register(ProductVersion)
class ProductVersionAdmin(admin.ModelAdmin):
    list_display = ('product', 'version', 'created_at')
    list_filter = ('product',)
    search_fields = ('product__name', 'version')
    ordering = ('-created_at',)