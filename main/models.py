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


class Wallet(models.Model):
    """A DEMO wallet for the Mobile Money Wallet Simulator. Fake money only."""
    nickname = models.CharField(max_length=20)                      # a made-up nickname, never a real name
    wallet_number = models.CharField(max_length=12, unique=True)    # made-up number like DW-482915
    balance = models.PositiveBigIntegerField(default=0)             # fake RWF, whole francs only
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # newest wallet first

    def __str__(self):
        return f"{self.nickname} ({self.wallet_number})"


class Transfer(models.Model):
    """One demo transfer of fake money from one wallet to another (stage 2), with a fee (stage 3)."""
    sender = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='sent_transfers')
    receiver = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='received_transfers')
    amount = models.PositiveBigIntegerField()                       # fake RWF the receiver gets
    fee = models.PositiveBigIntegerField(default=0)                 # fake RWF fee paid by the sender on top (goes to the Demo Operator)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # newest transfer first

    def __str__(self):
        return f"{self.sender.wallet_number} to {self.receiver.wallet_number}: {self.amount} RWF (fee {self.fee})"