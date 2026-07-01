def notifications(request):
    """
    Globally provides the unread notifications count and latest unread notifications
    for the logged-in user to all templates.
    """
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': request.user.notifications.filter(is_read=False).count(),
            'latest_notifications': request.user.notifications.filter(is_read=False)[:5]
        }
    return {
        'unread_notifications_count': 0,
        'latest_notifications': []
    }
