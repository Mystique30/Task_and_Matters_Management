from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .decorators import login_required_custom, admin_required
from .forms import LoginForm, RegisterForm, UserCreateForm, UserEditForm, ProfileForm, PasswordChangeForm
from .models import Profile


# ============================================================
# AUTH VIEWS — Login, Register, Logout
# ============================================================

def login_view(request):
    """
    Handles user login.
    GET: Shows the login form.
    POST: Validates credentials and logs the user in.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm()

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    """
    Handles user registration.
    Creates a new User with 'member' role by default.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
            )
            messages.success(request, 'Account created! Please log in.')
            return redirect('login')

    return render(request, 'accounts/register.html', {'form': form})


def logout_view(request):
    """Logs the user out and redirects to login page."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ============================================================
# PROFILE VIEW
# ============================================================

@login_required_custom
def profile_view(request):
    """Allows users to view and edit their own profile."""
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            request.user.email = form.cleaned_data['email']
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.save()

            request.user.profile.phone = form.cleaned_data['phone']
            request.user.profile.save()

            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = ProfileForm(initial={
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'phone': request.user.profile.phone if hasattr(request.user, 'profile') else '',
        })

    return render(request, 'accounts/profile.html', {'form': form})


@login_required_custom
def change_password_view(request):
    """Allows any logged-in user to change their own password."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save()
            # Re-authenticate so the session stays valid after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully!')
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})


# ============================================================
# USER ADMINISTRATION — Admin only
# ============================================================

@admin_required
def user_list_view(request):
    """Admin: List all users with their roles and status."""
    users = User.objects.select_related('profile').all().order_by('username')
    return render(request, 'accounts/user_list.html', {'users': users})


@admin_required
def user_create_view(request):
    """Admin: Create a new user with a specific role."""
    form = UserCreateForm()

    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data.get('first_name', ''),
                last_name=form.cleaned_data.get('last_name', ''),
            )
            # Ensure profile exists and set the role
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = form.cleaned_data['role']
            profile.save()

            messages.success(request, f'User "{user.username}" created successfully.')
            return redirect('user_list')

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Add New User',
    })


@admin_required
def user_edit_view(request, user_id):
    """Admin: Edit an existing user's details and role."""
    edit_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST)
        if form.is_valid():
            edit_user.email = form.cleaned_data['email']
            edit_user.first_name = form.cleaned_data['first_name']
            edit_user.last_name = form.cleaned_data['last_name']
            edit_user.is_active = form.cleaned_data['is_active']
            edit_user.save()

            profile, _ = Profile.objects.get_or_create(user=edit_user)
            profile.role = form.cleaned_data['role']
            profile.save()

            # If admin provided a new password for the user
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                edit_user.set_password(new_password)
                edit_user.save()
                if edit_user == request.user:
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, request.user)
                messages.success(request, f'User "{edit_user.username}" updated and password successfully changed.')
            else:
                messages.success(request, f'User "{edit_user.username}" updated successfully.')

            return redirect('user_list')
    else:
        form = UserEditForm(initial={
            'email': edit_user.email,
            'first_name': edit_user.first_name,
            'last_name': edit_user.last_name,
            'role': edit_user.profile.role if hasattr(edit_user, 'profile') else 'member',
            'is_active': edit_user.is_active,
        })

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'Edit User: {edit_user.username}',
        'edit_user': edit_user,
    })


@admin_required
def user_delete_view(request, user_id):
    """Admin: Delete a user (with confirmation)."""
    del_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        username = del_user.username
        del_user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('user_list')

    return render(request, 'accounts/user_confirm_delete.html', {
        'del_user': del_user,
    })


@admin_required
def user_detail_view(request, user_id):
    """
    Admin: View a user's assigned matters and tasks.
    Shows each matter with its tasks and completion status,
    plus standalone tasks not attached to any matter.
    """
    from matters.models import Matter, Task

    view_user = get_object_or_404(User, id=user_id)

    # Matters assigned to this user, prefetching tasks within those matters
    # that are also assigned to this user
    matters = (
        Matter.objects
        .filter(assigned_to=view_user)
        .prefetch_related('tasks')
        .order_by('-created_at')
    )

    # All tasks directly assigned to this user
    all_tasks = (
        Task.objects
        .filter(assigned_to=view_user)
        .select_related('matter')
        .order_by('-created_at')
    )

    # Tasks NOT linked to any of the assigned matters (standalone / cross-matter tasks)
    matter_ids = matters.values_list('id', flat=True)
    standalone_tasks = all_tasks.exclude(matter_id__in=matter_ids)

    # Per-user stats
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status='completed').count()
    in_progress_tasks = all_tasks.filter(status='in_progress').count()
    todo_tasks = all_tasks.filter(status='todo').count()

    return render(request, 'accounts/user_detail.html', {
        'view_user': view_user,
        'matters': matters,
        'standalone_tasks': standalone_tasks,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'todo_tasks': todo_tasks,
    })