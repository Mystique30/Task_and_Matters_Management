from matters.models import TimelineEntry, Notification


def log_timeline(user, action, description, matter=None, task=None):
    """
    Creates a timeline entry to track activity.
    Called whenever something important happens (create, edit, delete, etc.)
    """
    TimelineEntry.objects.create(
        action=action,
        description=description,
        user=user,
        matter=matter,
        task=task,
    )


def send_notification(user, message, link=''):
    """
    Creates an in-app notification for a user.
    Called when a task is assigned, a comment is added, etc.
    """
    Notification.objects.create(
        user=user,
        message=message,
        link=link,
    )
