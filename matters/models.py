from django.db import models
from django.contrib.auth.models import User


class Matter(models.Model):
    """
    A Matter is the top-level entity — like a project or case.
    Tasks belong to Matters. Think: Matter = Project, Task = To-Do item.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    due_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_matters'
    )
    assigned_users = models.ManyToManyField(
        User, blank=True,
        related_name='multi_assigned_matters'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='created_matters'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_all_assigned_users(self):
        """Returns all assigned users (M2M plus legacy single assignee)."""
        users = list(self.assigned_users.all())
        if self.assigned_to and self.assigned_to not in users:
            users.append(self.assigned_to)
        return users

    def get_assigned_users_display(self):
        """Returns a formatted string of all assigned user names."""
        users = self.get_all_assigned_users()
        if not users:
            return "Unassigned"
        return ", ".join(u.get_full_name() or u.username for u in users)

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.due_date and self.status != 'completed':
            return self.due_date < timezone.now().date()
        return False

    class Meta:
        ordering = ['-created_at']


class Task(models.Model):
    """
    A Task belongs to a Matter (optionally).
    Each task can be assigned to a user and has a status + priority.
    """
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    matter = models.ForeignKey(
        Matter, on_delete=models.CASCADE,
        related_name='tasks', null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    due_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tasks'
    )
    assigned_users = models.ManyToManyField(
        User, blank=True,
        related_name='multi_assigned_tasks'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='created_tasks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_all_assigned_users(self):
        """Returns all assigned users (M2M plus legacy single assignee)."""
        users = list(self.assigned_users.all())
        if self.assigned_to and self.assigned_to not in users:
            users.append(self.assigned_to)
        return users

    def get_assigned_users_display(self):
        """Returns a formatted string of all assigned user names."""
        users = self.get_all_assigned_users()
        if not users:
            return "Unassigned"
        return ", ".join(u.get_full_name() or u.username for u in users)

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.due_date and self.status != 'completed':
            return self.due_date < timezone.now().date()
        return False

    class Meta:
        ordering = ['-created_at']


class Document(models.Model):
    """File attachments linked to a Matter or Task."""
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/%Y/%m/')
    matter = models.ForeignKey(
        Matter, on_delete=models.CASCADE,
        related_name='documents', null=True, blank=True
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='documents', null=True, blank=True
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        related_name='assigned_documents', null=True, blank=True
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-uploaded_at']


class Comment(models.Model):
    """Comments on a Matter or Task."""
    text = models.TextField()
    matter = models.ForeignKey(
        Matter, on_delete=models.CASCADE,
        related_name='comments', null=True, blank=True
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='comments', null=True, blank=True
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author.username} on {self.created_at:%Y-%m-%d}"

    class Meta:
        ordering = ['-created_at']


class Reminder(models.Model):
    """Reminders with due dates, linked to Matters or Tasks."""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()
    matter = models.ForeignKey(
        Matter, on_delete=models.CASCADE,
        related_name='reminders', null=True, blank=True
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='reminders', null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        from django.utils import timezone
        return not self.is_completed and self.due_date < timezone.now()

    class Meta:
        ordering = ['due_date']


class Notification(models.Model):
    """In-app notifications for users."""
    message = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}"

    class Meta:
        ordering = ['-created_at']


class TimelineEntry(models.Model):
    """Activity log — records who did what, when."""
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
        ('commented', 'Commented'),
        ('assigned', 'Assigned'),
        ('status_changed', 'Status Changed'),
        ('document_uploaded', 'Document Uploaded'),
    ]

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    matter = models.ForeignKey(
        Matter, on_delete=models.SET_NULL,
        related_name='timeline_entries', null=True, blank=True
    )
    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL,
        related_name='timeline_entries', null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} {self.get_action_display()} - {self.description}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Timeline entries'


class ChatMessage(models.Model):
    """Live team chat and direct messages."""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chat_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_chat_messages', null=True, blank=True)
    room = models.CharField(max_length=50, default='general')  # 'general', 'matters', 'urgent' or 'dm'
    message = models.TextField()
    matter = models.ForeignKey(Matter, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_messages')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_messages')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.room}] {self.sender.username}: {self.message[:30]}"