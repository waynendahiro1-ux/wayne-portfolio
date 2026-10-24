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


class PaymentRequest(models.Model):
    """A demo payment request (stage 4). The wallet that creates it will RECEIVE the money.
    The QR code holds only a link to the pay page for this request's code."""
    code = models.CharField(max_length=8, unique=True)              # short random code used in the link
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='payment_requests')
    amount = models.PositiveBigIntegerField()                       # fake RWF being asked for
    status = models.CharField(max_length=10, default='open')        # open, paid or cancelled
    paid_by = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.SET_NULL, related_name='paid_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']  # newest request first

    def __str__(self):
        return f"{self.code}: {self.amount} RWF ({self.status})"


class Budget(models.Model):
    """A DEMO budget for the Budget Tracker (fintech project 5). Typed-in fake numbers only."""
    name = models.CharField(max_length=20)                          # a made-up name, never a real name
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # newest budget first

    def __str__(self):
        return self.name


class BudgetEntry(models.Model):
    """One line in a budget: money that came in (income) or went out (expense)."""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='entries')   # deleting a budget deletes its entries
    kind = models.CharField(max_length=10)                          # 'income' or 'expense' (worked out from the category)
    category = models.CharField(max_length=30)                      # for example Food or Pocket money
    label = models.CharField(max_length=30, blank=True)             # optional short note
    amount = models.PositiveBigIntegerField()                       # fake RWF, whole francs only
    date = models.DateField()                                       # the day the money moved
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']  # newest day first

    def __str__(self):
        return f"{self.date} {self.category}: {self.amount} RWF ({self.kind})"


class BudgetLimit(models.Model):
    """A spending limit for one category in one budget (stage 3). For example: Food, 20000 RWF."""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='limits')   # deleting a budget deletes its limits
    category = models.CharField(max_length=30)                      # a spending category, for example Food
    amount = models.PositiveBigIntegerField()                       # the limit in fake RWF, whole francs only
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category']
        constraints = [
            # only ONE limit per category in each budget (setting it again changes the old one)
            models.UniqueConstraint(fields=['budget', 'category'], name='one_limit_per_category'),
        ]

    def __str__(self):
        return f"{self.category}: limit {self.amount} RWF"