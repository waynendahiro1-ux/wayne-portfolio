from django.db import models


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name}: {self.subject or 'No subject'}"


class Game(models.Model):
    date = models.DateField()
    opponent = models.CharField(max_length=100)
    points = models.PositiveIntegerField(default=0)
    rebounds = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-date']  # newest game first

    def __str__(self):
        return f"{self.date} vs {self.opponent}"