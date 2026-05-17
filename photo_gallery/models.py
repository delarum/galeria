"""Models for the Photo Gallery app."""
from django.db import models
from django.contrib.auth.models import User
from taggit.managers import TaggableManager


class UserProfile(models.Model):
    """Extended profile linked 1-to-1 with Django's built-in User."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, max_length=500)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Photo(models.Model):
    """Represents a photo/artwork in the gallery."""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='photos/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='photos')
    tags = TaggableManager(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def total_likes(self):
        return self.interactions.filter(interaction_type='like').count()

    def total_dislikes(self):
        return self.interactions.filter(interaction_type='dislike').count()

    def user_interaction(self, user):
        if not user.is_authenticated:
            return None
        try:
            return self.interactions.get(user=user).interaction_type
        except PhotoInteraction.DoesNotExist:
            return None


class PhotoInteraction(models.Model):
    """Tracks likes/dislikes per user per photo."""
    LIKE = 'like'
    DISLIKE = 'dislike'
    INTERACTION_CHOICES = [(LIKE, 'Like'), (DISLIKE, 'Dislike')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interactions')
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='interactions')
    interaction_type = models.CharField(max_length=10, choices=INTERACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'photo')

    def __str__(self):
        return f"{self.user.username} {self.interaction_type}d {self.photo.title}"