from django.contrib import admin
from .models import Matter, Task, Document, Comment, Reminder, Notification, TimelineEntry


@admin.register(Matter)
class MatterAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'priority', 'assigned_to', 'due_date', 'created_by')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'description')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'matter', 'status', 'priority', 'assigned_to', 'due_date')
    list_filter = ('status', 'priority', 'matter')
    search_fields = ('title', 'description')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'matter', 'task', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'matter', 'task', 'created_at')
    list_filter = ('created_at',)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'due_date', 'is_completed')
    list_filter = ('is_completed', 'due_date')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)


@admin.register(TimelineEntry)
class TimelineEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'description', 'timestamp')
    list_filter = ('action',)
