from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from datetime import timedelta

from accounts.decorators import login_required_custom, manager_or_admin_required
from .models import Matter, Task, Document, Comment, Reminder, Notification, TimelineEntry
from .forms import MatterForm, TaskForm, MemberTaskStatusForm, DocumentForm, CommentForm, ReminderForm
from .utils import log_timeline, send_notification


# ============================================================
# AUTHORIZATION & QUERY FILTER HELPERS
# ============================================================

def get_user_matters_qs(user):
    """
    Returns the queryset of Matters visible to the given user:
    - Admin: All matters.
    - Manager: Only matters assigned to that manager (or created by them with no other manager assigned).
               Manager 1 must not see matters assigned to Manager 2, and vice versa.
    - Member: Only matters containing tasks assigned to that member.
    """
    profile = getattr(user, 'profile', None)
    if not profile or profile.is_admin:
        return Matter.objects.all()
    elif profile.is_manager:
        return Matter.objects.filter(
            Q(assigned_to=user) | Q(created_by=user, assigned_to__isnull=True)
        ).distinct()
    else:  # member
        return Matter.objects.filter(tasks__assigned_to=user).distinct()


def get_user_tasks_qs(user):
    """
    Returns the queryset of Tasks visible to the given user:
    - Admin: All tasks.
    - Manager: Only tasks within matters assigned to that manager, or tasks assigned directly to that manager.
               Manager 1 must not see matters/tasks assigned to Manager 2, and vice versa.
    - Member: Strictly only tasks assigned to themselves.
    """
    profile = getattr(user, 'profile', None)
    if not profile or profile.is_admin:
        return Task.objects.all()
    elif profile.is_manager:
        return Task.objects.filter(
            Q(matter__assigned_to=user) |
            Q(assigned_to=user) |
            Q(created_by=user, matter__assigned_to__isnull=True, matter__isnull=True)
        ).distinct()
    else:  # member
        return Task.objects.filter(assigned_to=user)


# ============================================================
# DASHBOARD
# ============================================================

@login_required_custom
def dashboard_view(request):
    """
    Main dashboard with 6 summary cards.
    Shows different data based on user role and assignments.
    """
    today = timezone.now().date()
    week_from_now = today + timedelta(days=7)
    user = request.user

    profile = getattr(user, 'profile', None)

    # Scoped querysets based on authorization rules
    matters_qs = get_user_matters_qs(user)
    tasks_qs = get_user_tasks_qs(user)

    # Counts for the 6 dashboard cards
    active_matters = matters_qs.filter(status='active').count()
    matters_due = matters_qs.filter(
        due_date__lte=week_from_now,
        due_date__gte=today,
        status='active'
    ).count()
    overdue_matters = matters_qs.filter(
        due_date__lt=today,
        status='active'
    ).count()
    overdue_tasks = tasks_qs.filter(
        due_date__lt=today
    ).exclude(status='completed').count()
    upcoming_tasks = tasks_qs.filter(
        due_date__gte=today,
        due_date__lte=week_from_now
    ).exclude(status='completed').count()
    personal_tasks = tasks_qs.filter(
        assigned_to=user
    ).exclude(status='completed').count()

    # Lists for dashboard cards
    active_matters_list = matters_qs.filter(
        status='active'
    ).select_related('assigned_to')[:5]

    matters_due_list = matters_qs.filter(
        due_date__lte=week_from_now,
        due_date__gte=today,
        status='active'
    ).select_related('assigned_to')[:5]

    overdue_tasks_list = tasks_qs.filter(
        due_date__lt=today
    ).exclude(status='completed').select_related('assigned_to', 'matter')[:5]

    overdue_matters_list = matters_qs.filter(
        due_date__lt=today,
        status='active'
    ).select_related('assigned_to')[:5]

    # Recent updates (last 10 timeline entries scoped to visible items)
    if not profile or profile.is_admin:
        recent_updates = TimelineEntry.objects.select_related('user', 'matter', 'task')[:10]
    else:
        recent_updates = TimelineEntry.objects.filter(
            Q(task__in=tasks_qs) | Q(matter__in=matters_qs) | Q(user=user)
        ).distinct().select_related('user', 'matter', 'task')[:10]

    # Upcoming tasks list
    upcoming_tasks_list = tasks_qs.filter(
        due_date__gte=today,
        due_date__lte=week_from_now
    ).exclude(status='completed').select_related('assigned_to', 'matter')[:5]

    # Personal tasks list
    personal_tasks_list = tasks_qs.filter(
        assigned_to=user
    ).exclude(status='completed').select_related('matter')[:5]

    # Unread notifications count
    unread_notifications = Notification.objects.filter(
        user=user, is_read=False
    ).count()

    context = {
        'active_matters': active_matters,
        'matters_due': matters_due,
        'overdue_count': overdue_matters + overdue_tasks,
        'upcoming_tasks': upcoming_tasks,
        'personal_tasks': personal_tasks,
        'active_matters_list': active_matters_list,
        'matters_due_list': matters_due_list,
        'overdue_tasks_list': overdue_tasks_list,
        'overdue_matters_list': overdue_matters_list,
        'recent_updates': recent_updates,
        'upcoming_tasks_list': upcoming_tasks_list,
        'personal_tasks_list': personal_tasks_list,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'matters/dashboard.html', context)


@login_required_custom
def dashboard_task_status_update(request, task_id):
    """
    AJAX endpoint to update a task's status from the dashboard.
    Accepts POST with 'status' field.
    """
    from django.http import JsonResponse

    task = get_object_or_404(Task, id=task_id)
    if not get_user_tasks_qs(request.user).filter(id=task.id).exists():
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        valid_statuses = [choice[0] for choice in Task.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

        old_status = task.get_status_display()
        task.status = new_status
        task.save()

        # Log the timeline entry
        log_timeline(
            user=request.user,
            action='status_changed',
            description=f'Task "{task.title}" status changed from {old_status} to {task.get_status_display()}',
            task=task,
            matter=task.matter,
        )

        return JsonResponse({
            'success': True,
            'new_status': new_status,
            'new_status_display': task.get_status_display(),
        })

    return JsonResponse({'success': False, 'error': 'POST required'}, status=405)


# ============================================================
# MATTERS — CRUD
# ============================================================

@login_required_custom
def matter_list_view(request):
    """List all matters with optional status filter."""
    status_filter = request.GET.get('status', '')
    matters = get_user_matters_qs(request.user).select_related('assigned_to', 'created_by')

    if status_filter:
        matters = matters.filter(status=status_filter)

    return render(request, 'matters/matter_list.html', {
        'matters': matters,
        'status_filter': status_filter,
    })


@manager_or_admin_required
def matter_create_view(request):
    """Create a new matter (Admin/Manager only)."""
    form = MatterForm()

    if request.method == 'POST':
        form = MatterForm(request.POST)
        if form.is_valid():
            matter = form.save(commit=False)
            matter.created_by = request.user
            matter.save()

            log_timeline(request.user, 'created', f'Created matter: {matter.title}', matter=matter)

            if matter.assigned_to and matter.assigned_to != request.user:
                send_notification(
                    matter.assigned_to,
                    f'You have been assigned to matter: {matter.title}',
                    link=f'/matters/{matter.id}/'
                )

            messages.success(request, 'Matter created successfully.')
            return redirect('matter_detail', matter_id=matter.id)

    return render(request, 'matters/matter_form.html', {
        'form': form,
        'title': 'Create New Matter',
    })


@login_required_custom
def matter_detail_view(request, matter_id):
    """View matter details with its tasks, comments, and documents."""
    matter = get_object_or_404(Matter, id=matter_id)

    # Authorization check: user must be permitted to see this matter
    if not get_user_matters_qs(request.user).filter(id=matter.id).exists():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('matter_list')

    # Tasks within this matter visible to current user
    tasks = get_user_tasks_qs(request.user).filter(matter=matter).select_related('assigned_to')

    comments = matter.comments.select_related('author')
    documents = matter.documents.select_related('uploaded_by')
    comment_form = CommentForm()

    return render(request, 'matters/matter_detail.html', {
        'matter': matter,
        'tasks': tasks,
        'comments': comments,
        'documents': documents,
        'comment_form': comment_form,
    })


@manager_or_admin_required
def matter_edit_view(request, matter_id):
    """Edit a matter (Admin/Manager only)."""
    matter = get_object_or_404(Matter, id=matter_id)

    if not get_user_matters_qs(request.user).filter(id=matter.id).exists():
        messages.error(request, 'You do not have permission to edit this matter.')
        return redirect('matter_list')

    form = MatterForm(instance=matter)

    if request.method == 'POST':
        form = MatterForm(request.POST, instance=matter)
        if form.is_valid():
            matter = form.save()
            log_timeline(request.user, 'updated', f'Updated matter: {matter.title}', matter=matter)
            messages.success(request, 'Matter updated successfully.')
            return redirect('matter_detail', matter_id=matter.id)

    return render(request, 'matters/matter_form.html', {
        'form': form,
        'title': f'Edit Matter: {matter.title}',
        'matter': matter,
    })


@manager_or_admin_required
def matter_delete_view(request, matter_id):
    """Delete a matter with confirmation (Admin/Manager only)."""
    matter = get_object_or_404(Matter, id=matter_id)

    if not get_user_matters_qs(request.user).filter(id=matter.id).exists():
        messages.error(request, 'You do not have permission to delete this matter.')
        return redirect('matter_list')

    if request.method == 'POST':
        title = matter.title
        log_timeline(request.user, 'deleted', f'Deleted matter: {title}')
        matter.delete()
        messages.success(request, f'Matter "{title}" deleted.')
        return redirect('matter_list')

    return render(request, 'matters/matter_confirm_delete.html', {'matter': matter})


# ============================================================
# TASKS — CRUD
# ============================================================

@login_required_custom
def task_list_view(request):
    """List all tasks with optional filters."""
    status_filter = request.GET.get('status', '')
    tasks = get_user_tasks_qs(request.user).select_related('assigned_to', 'created_by', 'matter')

    if status_filter:
        tasks = tasks.filter(status=status_filter)

    return render(request, 'matters/task_list.html', {
        'tasks': tasks,
        'status_filter': status_filter,
    })


@manager_or_admin_required
def task_create_view(request):
    """Create a new task (Admin/Manager only)."""
    form = TaskForm()

    # Pre-fill matter if provided in URL
    matter_id = request.GET.get('matter')
    if matter_id:
        form.initial['matter'] = matter_id

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()

            log_timeline(
                request.user, 'created',
                f'Created task: {task.title}',
                matter=task.matter, task=task
            )

            if task.assigned_to and task.assigned_to != request.user:
                send_notification(
                    task.assigned_to,
                    f'You have been assigned task: {task.title}',
                    link=f'/tasks/{task.id}/'
                )

            messages.success(request, 'Task created successfully.')
            return redirect('task_detail', task_id=task.id)

    return render(request, 'matters/task_form.html', {
        'form': form,
        'title': 'Create New Task',
    })


@login_required_custom
def task_detail_view(request, task_id):
    """View task details with comments and documents."""
    task = get_object_or_404(Task, id=task_id)

    # Authorization check: task must be visible to current user
    if not get_user_tasks_qs(request.user).filter(id=task.id).exists():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('task_list')

    comments = task.comments.select_related('author')
    documents = task.documents.select_related('uploaded_by')
    comment_form = CommentForm()

    return render(request, 'matters/task_detail.html', {
        'task': task,
        'comments': comments,
        'documents': documents,
        'comment_form': comment_form,
    })


@login_required_custom
def task_edit_view(request, task_id):
    """
    Edit a task.
    - Admins and Managers can edit all fields of authorized tasks.
    - Members can only edit the status of tasks assigned to them.
    """
    task = get_object_or_404(Task, id=task_id)

    # Authorization check: user must be permitted to view and edit this task
    if not get_user_tasks_qs(request.user).filter(id=task.id).exists():
        messages.error(request, 'You do not have permission to edit this task.')
        return redirect('task_list')

    profile = getattr(request.user, 'profile', None)
    is_admin_or_mgr = profile and (profile.is_admin or profile.is_manager)
    is_assigned_member = (task.assigned_to == request.user)

    # If the user is a Member, ensure the task is assigned to them
    if not is_admin_or_mgr:
        if not is_assigned_member:
            messages.error(request, 'You do not have permission to edit this task.')
            return redirect('task_list')

    # Choose form: Admins/Managers get the full form; Members get only the status field
    form_class = TaskForm if is_admin_or_mgr else MemberTaskStatusForm

    if request.method == 'POST':
        form = form_class(request.POST, instance=task)
        if form.is_valid():
            old_status = Task.objects.get(id=task_id).status
            task = form.save()

            if old_status != task.status:
                log_timeline(
                    request.user, 'status_changed',
                    f'Changed task "{task.title}" status from {old_status} to {task.get_status_display()}',
                    matter=task.matter, task=task
                )
            else:
                log_timeline(
                    request.user, 'updated',
                    f'Updated task: {task.title}',
                    matter=task.matter, task=task
                )

            messages.success(request, 'Task updated successfully.')
            return redirect('task_detail', task_id=task.id)
    else:
        form = form_class(instance=task)

    title = f'Edit Task: {task.title}' if is_admin_or_mgr else f'Update Status: {task.title}'

    return render(request, 'matters/task_form.html', {
        'form': form,
        'title': title,
        'task': task,
        'is_member_edit': not is_admin_or_mgr,
    })


@manager_or_admin_required
def task_delete_view(request, task_id):
    """Delete a task with confirmation (Admin/Manager only)."""
    task = get_object_or_404(Task, id=task_id)

    if not get_user_tasks_qs(request.user).filter(id=task.id).exists():
        messages.error(request, 'You do not have permission to delete this task.')
        return redirect('task_list')

    if request.method == 'POST':
        title = task.title
        log_timeline(request.user, 'deleted', f'Deleted task: {title}', matter=task.matter)
        task.delete()
        messages.success(request, f'Task "{title}" deleted.')
        return redirect('task_list')

    return render(request, 'matters/task_confirm_delete.html', {'task': task})


# ============================================================
# DOCUMENTS
# ============================================================

@login_required_custom
def document_list_view(request):
    """List all documents."""
    documents = Document.objects.select_related('uploaded_by', 'matter', 'task')
    return render(request, 'matters/document_list.html', {'documents': documents})


@login_required_custom
def document_upload_view(request):
    """Upload a new document."""
    form = DocumentForm()

    matter_id = request.GET.get('matter')
    task_id = request.GET.get('task')
    if matter_id:
        form.initial['matter'] = matter_id
    if task_id:
        form.initial['task'] = task_id

    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()

            log_timeline(
                request.user, 'document_uploaded',
                f'Uploaded document: {doc.title}',
                matter=doc.matter, task=doc.task
            )
            messages.success(request, 'Document uploaded successfully.')
            return redirect('document_list')

    return render(request, 'matters/document_form.html', {
        'form': form,
        'title': 'Upload Document',
    })


@manager_or_admin_required
def document_delete_view(request, doc_id):
    """Delete a document."""
    doc = get_object_or_404(Document, id=doc_id)

    if request.method == 'POST':
        doc.delete()
        messages.success(request, 'Document deleted.')
        return redirect('document_list')

    return render(request, 'matters/document_confirm_delete.html', {'document': doc})


# ============================================================
# COMMENTS
# ============================================================

@login_required_custom
def comment_add_view(request):
    """Add a comment to a matter or task (POST only)."""
    if request.method == 'POST':
        form = CommentForm(request.POST)
        matter_id = request.POST.get('matter_id')
        task_id = request.POST.get('task_id')

        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = request.user

            if matter_id:
                matter = get_object_or_404(Matter, id=matter_id)
                comment.matter = matter
                comment.save()
                log_timeline(
                    request.user, 'commented',
                    f'Commented on matter: {matter.title}',
                    matter=matter
                )
                messages.success(request, 'Comment added.')
                return redirect('matter_detail', matter_id=matter_id)

            elif task_id:
                task = get_object_or_404(Task, id=task_id)
                comment.task = task
                comment.save()
                log_timeline(
                    request.user, 'commented',
                    f'Commented on task: {task.title}',
                    task=task, matter=task.matter
                )
                messages.success(request, 'Comment added.')
                return redirect('task_detail', task_id=task_id)

    return redirect('dashboard')


@login_required_custom
def comment_list_view(request):
    """List all comments."""
    comments = Comment.objects.select_related('author', 'matter', 'task')
    return render(request, 'matters/comment_list.html', {'comments': comments})


# ============================================================
# REMINDERS
# ============================================================

@login_required_custom
def reminder_list_view(request):
    """List user's reminders."""
    reminders = Reminder.objects.filter(user=request.user).select_related('matter', 'task')
    return render(request, 'matters/reminder_list.html', {'reminders': reminders})


@login_required_custom
def reminder_create_view(request):
    """Create a new reminder."""
    form = ReminderForm()

    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            reminder.save()
            messages.success(request, 'Reminder created.')
            return redirect('reminder_list')

    return render(request, 'matters/reminder_form.html', {
        'form': form,
        'title': 'Create Reminder',
    })


@login_required_custom
def reminder_complete_view(request, reminder_id):
    """Mark a reminder as completed."""
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    reminder.is_completed = True
    reminder.save()
    messages.success(request, 'Reminder completed.')
    return redirect('reminder_list')


@login_required_custom
def reminder_delete_view(request, reminder_id):
    """Delete a reminder."""
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)

    if request.method == 'POST':
        reminder.delete()
        messages.success(request, 'Reminder deleted.')
        return redirect('reminder_list')

    return render(request, 'matters/reminder_confirm_delete.html', {'reminder': reminder})


# ============================================================
# TIMELINE
# ============================================================

@login_required_custom
def timeline_view(request):
    """
    Show activity timeline organized into Matter cards.
    Each Matter card contains its tasks.
    Clicking any task reveals the chronological timeline of what was done throughout that task.
    Strictly isolated: managers only see their own assigned matters, tasks, and changes.
    """
    user = request.user
    user_matters = get_user_matters_qs(user).order_by('-created_at')
    user_tasks = get_user_tasks_qs(user).order_by('due_date', 'id')

    # Prefetch timeline entries for tasks visible to this user
    task_timeline_prefetch = Prefetch(
        'timeline_entries',
        queryset=TimelineEntry.objects.select_related('user').order_by('-timestamp')
    )

    # Prefetch tasks within each matter
    tasks_prefetch = Prefetch(
        'tasks',
        queryset=user_tasks.select_related('assigned_to').prefetch_related(task_timeline_prefetch)
    )

    matters = user_matters.prefetch_related(
        tasks_prefetch
    ).select_related('assigned_to', 'created_by')

    return render(request, 'matters/timeline.html', {
        'matters': matters,
    })


# ============================================================
# SEARCH
# ============================================================

@login_required_custom
def search_view(request):
    """Search across matters and tasks."""
    query = request.GET.get('q', '').strip()
    matters = []
    tasks = []

    if query:
        matters = get_user_matters_qs(request.user).filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        ).select_related('assigned_to')
        tasks = get_user_tasks_qs(request.user).filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        ).select_related('assigned_to', 'matter')

    return render(request, 'matters/search_results.html', {
        'query': query,
        'matters': matters,
        'tasks': tasks,
    })


# ============================================================
# NOTIFICATIONS
# ============================================================

@login_required_custom
def notification_list_view(request):
    """List all notifications for the user."""
    notifications = Notification.objects.filter(user=request.user)
    return render(request, 'matters/notification_list.html', {
        'notifications': notifications,
    })


@login_required_custom
def notification_mark_read_view(request, notif_id):
    """Mark a single notification as read."""
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.is_read = True
    notif.save()

    if notif.link:
        return redirect(notif.link)
    return redirect('notification_list')


@login_required_custom
def notification_mark_all_read_view(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')


# ============================================================
# REPORTS
# ============================================================

@login_required_custom
def reports_view(request):
    """Show reports and statistics."""
    today = timezone.now().date()

    context = {
        'total_matters': Matter.objects.count(),
        'active_matters': Matter.objects.filter(status='active').count(),
        'completed_matters': Matter.objects.filter(status='completed').count(),
        'on_hold_matters': Matter.objects.filter(status='on_hold').count(),
        'overdue_matters': Matter.objects.filter(due_date__lt=today, status='active').count(),

        'total_tasks': Task.objects.count(),
        'todo_tasks': Task.objects.filter(status='todo').count(),
        'in_progress_tasks': Task.objects.filter(status='in_progress').count(),
        'completed_tasks': Task.objects.filter(status='completed').count(),
        'overdue_tasks': Task.objects.filter(due_date__lt=today).exclude(status='completed').count(),

        'total_documents': Document.objects.count(),
        'total_comments': Comment.objects.count(),

        'users_by_role': {
            'admins': User.objects.filter(profile__role='admin').count(),
            'managers': User.objects.filter(profile__role='manager').count(),
            'members': User.objects.filter(profile__role='member').count(),
        },
    }
    return render(request, 'matters/reports.html', context)