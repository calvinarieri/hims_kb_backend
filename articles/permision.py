from rest_framework import permissions


class IsStaffOrAdminUser(permissions.BasePermission):
    """
    Allows read/write access only to staff members and superusers (admins).
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class CanReadArticle(permissions.BasePermission):
    """
    Controls read access based on article visibility and status:
    - PUBLIC + PUBLISHED: Anyone can read.
    - PRIVATE or DRAFT: Only staff/admins can read.
    """
    def has_object_permission(self, request, view, obj):
        is_staff_or_admin = request.user and request.user.is_authenticated and request.user.is_staff
        
        if is_staff_or_admin:
            return True
            
        return obj.visibility == 'PUBLIC' and obj.status == 'PUBLISHED'


class IsAuthorOrAdminForWrite(permissions.BasePermission):
    """
    Staff members can update/delete ONLY articles they authored.
    Admins (superusers) have full access to edit/delete any article.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
            
        if request.user.is_superuser:
            return True
            
        # Check if the requesting user authored any version of this article
        return obj.versions.filter(author=request.user).exists()