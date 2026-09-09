from django import forms
from django.contrib.auth.models import User
from .models import Matter, Task, Document, Comment, Reminder


class MatterForm(forms.ModelForm):
    document = forms.FileField(
        required=False,
        label="Attach Document (optional)",
        widget=forms.FileInput(attrs={'class': 'form-input'})
    )
    document_title = forms.CharField(
        required=False,
        label="Document Title (optional)",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Leave blank to use file name',
        })
    )

    class Meta:
        model = Matter
        fields = ['title', 'description', 'status', 'priority', 'due_date', 'assigned_users']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Matter title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Describe this matter...',
                'rows': 4,
            }),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'priority': forms.Select(attrs={'class': 'form-input'}),
            'due_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
            'assigned_users': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'assigned_users': 'Assign To',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_users'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['assigned_users'].required = False
        if self.instance and self.instance.pk:
            # Include both assigned_users and any legacy assigned_to
            initial_users = list(self.instance.assigned_users.all())
            if self.instance.assigned_to and self.instance.assigned_to not in initial_users:
                initial_users.append(self.instance.assigned_to)
            self.fields['assigned_users'].initial = initial_users

    def save(self, commit=True):
        instance = super().save(commit=False)
        assigned_users = self.cleaned_data.get('assigned_users')
        if assigned_users and assigned_users.exists():
            instance.assigned_to = assigned_users.first()
        else:
            instance.assigned_to = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class TaskForm(forms.ModelForm):
    document = forms.FileField(
        required=False,
        label="Attach Document (optional)",
        widget=forms.FileInput(attrs={'class': 'form-input'})
    )
    document_title = forms.CharField(
        required=False,
        label="Document Title (optional)",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Leave blank to use file name',
        })
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'matter', 'status', 'priority', 'due_date', 'assigned_users']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Task title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Describe this task...',
                'rows': 4,
            }),
            'matter': forms.Select(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'priority': forms.Select(attrs={'class': 'form-input'}),
            'due_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
            'assigned_users': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'assigned_users': 'Assign To',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_users'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['assigned_users'].required = False
        self.fields['matter'].required = False
        if self.instance and self.instance.pk:
            initial_users = list(self.instance.assigned_users.all())
            if self.instance.assigned_to and self.instance.assigned_to not in initial_users:
                initial_users.append(self.instance.assigned_to)
            self.fields['assigned_users'].initial = initial_users

    def save(self, commit=True):
        instance = super().save(commit=False)
        assigned_users = self.cleaned_data.get('assigned_users')
        if assigned_users and assigned_users.exists():
            instance.assigned_to = assigned_users.first()
        else:
            instance.assigned_to = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class MemberTaskStatusForm(forms.ModelForm):
    """
    Form for members to update ONLY the status of tasks assigned to them.
    Django automatically restricts incoming POST data to only the fields listed here.
    """
    class Meta:
        model = Task
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-input'}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file', 'matter', 'task', 'assigned_to']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Document title',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-input',
            }),
            'matter': forms.Select(attrs={'class': 'form-input'}),
            'task': forms.Select(attrs={'class': 'form-input'}),
            'assigned_to': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matter'].required = False
        self.fields['task'].required = False
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].label = "Assign To (Manager or Member)"
        self.fields['assigned_to'].empty_label = "— Unassigned (Admin Only) —"


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Write a comment...',
                'rows': 3,
            }),
        }


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ['title', 'description', 'due_date', 'matter', 'task']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Reminder title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Details...',
                'rows': 3,
            }),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
            'matter': forms.Select(attrs={'class': 'form-input'}),
            'task': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matter'].required = False
        self.fields['task'].required = False
