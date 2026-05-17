"""
Views for the Photo Gallery app.
Covers: gallery, photo detail, like/dislike, auth, profile management.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from taggit.models import Tag

from .models import Photo, UserProfile, PhotoInteraction
from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm, PhotoUploadForm
from django.contrib.auth.models import User
import json


# ── Signals (create profile on user save) ────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create a UserProfile whenever a new User is created."""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


# ── Gallery ───────────────────────────────────────────────────────────────────

def gallery(request):
    """Homepage: display all photos, support tag filtering and search."""
    photos = Photo.objects.prefetch_related('tags').all()
    all_tags = Tag.objects.all()
    selected_tag = request.GET.get('tag', '')
    search_query = request.GET.get('q', '')

    if selected_tag:
        photos = photos.filter(tags__name__in=[selected_tag]).distinct()

    if search_query:
        photos = photos.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    context = {
        'photos': photos,
        'all_tags': all_tags,
        'selected_tag': selected_tag,
        'search_query': search_query,
    }
    return render(request, 'photo_gallery/gallery.html', context)


def photo_detail(request, pk):
    """Detail page for a single photo."""
    photo = get_object_or_404(Photo, pk=pk)
    user_interaction = photo.user_interaction(request.user)
    related_photos = Photo.objects.filter(
        tags__in=photo.tags.all()
    ).exclude(pk=pk).distinct()[:4]

    context = {
        'photo': photo,
        'user_interaction': user_interaction,
        'related_photos': related_photos,
    }
    return render(request, 'photo_gallery/photo_detail.html', context)


@login_required
def toggle_interaction(request, pk):
    """AJAX endpoint: like or dislike a photo. Toggles off if already set."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    photo = get_object_or_404(Photo, pk=pk)
    data = json.loads(request.body)
    action = data.get('action')  # 'like' or 'dislike'

    if action not in ('like', 'dislike'):
        return JsonResponse({'error': 'Invalid action'}, status=400)

    interaction, created = PhotoInteraction.objects.get_or_create(
        user=request.user, photo=photo,
        defaults={'interaction_type': action}
    )

    if not created:
        if interaction.interaction_type == action:
            # Toggle off
            interaction.delete()
            current = None
        else:
            # Switch from like to dislike or vice versa
            interaction.interaction_type = action
            interaction.save()
            current = action
    else:
        current = action

    return JsonResponse({
        'likes': photo.total_likes(),
        'dislikes': photo.total_dislikes(),
        'user_interaction': current,
    })


@login_required
def upload_photo(request):
    """Upload a new photo (authenticated users only)."""
    if request.method == 'POST':
        form = PhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.uploaded_by = request.user
            photo.save()
            form.save_m2m()  # Save tags
            messages.success(request, 'Photo uploaded successfully!')
            return redirect('photo_detail', pk=photo.pk)
    else:
        form = PhotoUploadForm()
    return render(request, 'photo_gallery/upload_photo.html', {'form': form})


# ── Authentication ────────────────────────────────────────────────────────────

def register(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('gallery')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account has been created.')
            return redirect('gallery')
    else:
        form = RegisterForm()
    return render(request, 'photo_gallery/register.html', {'form': form})


def user_login(request):
    """Login view."""
    if request.user.is_authenticated:
        return redirect('gallery')
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            next_url = request.GET.get('next', 'gallery')
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    return render(request, 'photo_gallery/login.html', {'form': form})


def user_logout(request):
    """Logout view."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('gallery')


# ── Profile ───────────────────────────────────────────────────────────────────

@login_required
def profile(request):
    """View and edit the current user's profile."""
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile_obj)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile_obj)

    user_photos = Photo.objects.filter(uploaded_by=request.user)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user_photos': user_photos,
    }
    return render(request, 'photo_gallery/profile.html', context)


@login_required
def change_password(request):
    """Change password view."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Password changed successfully!')
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'photo_gallery/change_password.html', {'form': form})


def public_profile(request, username):
    """Public-facing profile page for any user."""
    user = get_object_or_404(User, username=username)
    profile_obj, _ = UserProfile.objects.get_or_create(user=user)
    user_photos = Photo.objects.filter(uploaded_by=user)
    return render(request, 'photo_gallery/public_profile.html', {
        'profile_user': user,
        'profile_obj': profile_obj,
        'user_photos': user_photos,
    })