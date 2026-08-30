from rest_framework.permissions import BasePermission


class IsQueueStaff(BasePermission):
    """
    Allow queue-operation endpoints only to authenticated Django staff users.

    Smart Q does not yet have a dedicated staff-role model. Django's existing
    `is_staff` flag gives us a safe boundary now, instead of allowing every
    authenticated customer to operate counters. A richer role/branch permission
    system can replace this class later without changing every API view.
    """

    message = "Only authorised staff members can operate queue counters."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )
