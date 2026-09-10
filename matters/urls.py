from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/task/<int:task_id>/status/', views.dashboard_task_status_update, name='dashboard_task_status_update'),

    # Matters CRUD
    path('matters/', views.matter_list_view, name='matter_list'),
    path('matters/create/', views.matter_create_view, name='matter_create'),
    path('matters/<int:matter_id>/', views.matter_detail_view, name='matter_detail'),
    path('matters/<int:matter_id>/edit/', views.matter_edit_view, name='matter_edit'),
    path('matters/<int:matter_id>/delete/', views.matter_delete_view, name='matter_delete'),

    # Tasks CRUD
    path('tasks/', views.task_list_view, name='task_list'),
    path('tasks/create/', views.task_create_view, name='task_create'),
    path('tasks/<int:task_id>/', views.task_detail_view, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.task_edit_view, name='task_edit'),
    path('tasks/<int:task_id>/delete/', views.task_delete_view, name='task_delete'),

    # Documents
    path('documents/', views.document_list_view, name='document_list'),
    path('documents/upload/', views.document_upload_view, name='document_upload'),
    path('documents/<int:doc_id>/edit/', views.document_edit_view, name='document_edit'),
    path('documents/<int:doc_id>/delete/', views.document_delete_view, name='document_delete'),

    # Comments
    path('comments/', views.comment_list_view, name='comment_list'),
    path('comments/add/', views.comment_add_view, name='comment_add'),

    # Reminders
    path('reminders/', views.reminder_list_view, name='reminder_list'),
    path('reminders/create/', views.reminder_create_view, name='reminder_create'),
    path('reminders/<int:reminder_id>/complete/', views.reminder_complete_view, name='reminder_complete'),
    path('reminders/<int:reminder_id>/delete/', views.reminder_delete_view, name='reminder_delete'),

    # Timeline
    path('timeline/', views.timeline_view, name='timeline'),

    # Search
    path('search/', views.search_view, name='search'),

    # Notifications
    path('notifications/', views.notification_list_view, name='notification_list'),
    path('notifications/<int:notif_id>/read/', views.notification_mark_read_view, name='notification_mark_read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read_view, name='notification_mark_all_read'),

    # Reports
    path('reports/', views.reports_view, name='reports'),

    # Live Chat
    path('chat/', views.live_chat_view, name='live_chat'),
    path('chat/api/messages/', views.chat_api_messages, name='chat_api_messages'),
    path('chat/api/send/', views.chat_api_send, name='chat_api_send'),

    # Real-time Auto-Sync State Check
    path('api/sync-state/', views.api_sync_state, name='api_sync_state'),
]