import json
import logging
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import ContactForm
from .models import Game

logger = logging.getLogger(__name__)


def send_contact_email(data):
    """Send the message to my inbox using the Resend web API. Returns True if it worked."""
    if not settings.RESEND_API_KEY:
        logger.error("RESEND_API_KEY is not set")
        return False

    payload = {
        'from': 'Wayne Portfolio <onboarding@resend.dev>',
        'to': [settings.CONTACT_RECIPIENT],
        'reply_to': data['email'],
        'subject': f"Portfolio message: {data['subject'] or 'No subject'}",
        'text': (
            f"Name: {data['name']}\n"
            f"Email: {data['email']}\n"
            f"Subject: {data['subject'] or 'No subject'}\n\n"
            f"{data['message']}"
        ),
    }
    request = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {settings.RESEND_API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'wayne-portfolio/1.0',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as error:
        logger.error("Resend rejected the email: %s %s", error.code, error.read().decode('utf-8', 'ignore'))
    except Exception:
        logger.exception("Could not send contact email")
    return False


def home(request):
    return render(request, 'main/home.html')

def about(request):
    return render(request, 'main/about.html')

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            if send_contact_email(form.cleaned_data):
                messages.success(request, "Thanks! Your message has been sent. I'll get back to you soon.")
                return redirect(reverse('contact') + '#send-message')
            messages.error(request, "Sorry, your message could not be sent right now. Please email me directly instead.")
    else:
        form = ContactForm()
    return render(request, 'main/contact.html', {'form': form})

def basketball(request):
    # NEW: the stats tracker
    games = Game.objects.all()          # newest game first
    total_games = games.count()

    stats = None
    if total_games > 0:
        total_points = sum(g.points for g in games)
        total_rebounds = sum(g.rebounds for g in games)
        total_assists = sum(g.assists for g in games)
        stats = {
            'games': total_games,
            'ppg': round(total_points / total_games, 1),
            'rpg': round(total_rebounds / total_games, 1),
            'apg': round(total_assists / total_games, 1),
            'best': max(g.points for g in games),
        }

    return render(request, 'main/basketball.html', {'games': games, 'stats': stats})

def fintech(request):
    return render(request, 'main/fintech.html')

def gallery(request):
    folder = Path(__file__).resolve().parent / 'static' / 'main' / 'gallery'
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    photos = []
    if folder.exists():
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() in exts:
                caption = p.stem.replace('-', ' ').replace('_', ' ').title()
                photos.append({'file': p.name, 'caption': caption})
    return render(request, 'main/gallery.html', {'photos': photos})


# ---------- Fintech project 1: Savings Goal Calculator ----------

def read_whole_number(text, label, errors, required=False):
    """Turn what the visitor typed into a whole number.
    If something is wrong, add a friendly message to the errors list and return None."""
    text = text.replace(',', '').replace(' ', '')   # allow "500,000" or "500 000"

    if text == '':
        if required:
            errors.append(f"Please enter {label}.")
        return None

    # isdecimal() is True only for digits 0-9, so letters, minus signs and dots are rejected
    if not text.isdecimal():
        errors.append(f"{label} must be a whole number like 500000 (no letters, minus signs or decimals).")
        return None

    number = int(text)
    if number > 1_000_000_000_000:
        errors.append(f"{label} is too big for this demo.")
        return None
    return number


def savings_goal(request):
    # What the visitor typed, so the boxes keep their values after pressing Calculate
    values = {'target': '', 'saved': '', 'monthly': '', 'months': ''}
    errors = []
    result = None

    if request.method == 'POST':
        values['target'] = request.POST.get('target', '').strip()
        values['saved'] = request.POST.get('saved', '').strip()
        values['monthly'] = request.POST.get('monthly', '').strip()
        values['months'] = request.POST.get('months', '').strip()

        # 1. Read and check each box
        target = read_whole_number(values['target'], 'Your target amount', errors, required=True)
        saved = read_whole_number(values['saved'], 'Amount already saved', errors)
        monthly = read_whole_number(values['monthly'], 'Monthly saving', errors)
        months = read_whole_number(values['months'], 'Number of months', errors)

        if saved is None:
            saved = 0   # blank "already saved" means 0

        # 2. Check the rules between the boxes
        if target == 0:
            errors.append("Your target amount must be more than 0.")
        if monthly == 0:
            errors.append("Monthly saving must be more than 0.")
        if months == 0:
            errors.append("Number of months must be more than 0.")
        if months is not None and months > 1200:
            errors.append("Please use 1,200 months (100 years) or less.")
        if monthly is not None and months is not None:
            errors.append("Fill in only ONE of 'Monthly saving' or 'Number of months', not both.")
        if monthly is None and months is None and not errors:
            errors.append("Fill in either 'Monthly saving' or 'Number of months'.")

        # 3. If everything is fine, do the maths
        if not errors:
            remaining = max(target - saved, 0)      # how much is still left to save
            percent = min(saved * 100 // target, 100)   # progress bar, 0 to 100

            if remaining == 0:
                result = {'done': True, 'percent': 100}
            elif monthly is not None:
                # Months needed = remaining / monthly, rounded UP to the next whole month.
                # (a + b - 1) // b is a way to round up using only whole numbers.
                months_needed = (remaining + monthly - 1) // monthly
                years, extra_months = divmod(months_needed, 12)
                result = {
                    'done': False,
                    'mode': 'months',
                    'remaining': remaining,
                    'months': months_needed,
                    'years': years,
                    'extra_months': extra_months,
                    'percent': percent,
                }
            else:
                # Monthly saving needed = remaining / months, rounded UP to a whole RWF
                monthly_needed = (remaining + months - 1) // months
                result = {
                    'done': False,
                    'mode': 'monthly',
                    'remaining': remaining,
                    'monthly': monthly_needed,
                    'months': months,
                    'percent': percent,
                }

    return render(request, 'main/project_savings_goal.html', {
        'values': values,
        'errors': errors,
        'result': result,
    })


# ---------- Fintech project 2: Loan and Interest Calculator ----------

def read_rate(text, label, errors):
    """Read an interest rate like 18 or 18.5. Adds a friendly error and returns None if wrong."""
    text = text.replace(' ', '').replace(',', '.')   # allow "18,5" as well as "18.5"

    if text == '':
        errors.append(f"Please enter {label}.")
        return None

    # Allow digits with at most ONE dot. This rejects letters and minus signs.
    if len(text) > 8 or not text.replace('.', '', 1).isdecimal():
        errors.append(f"{label} must be a number like 18 or 18.5 (no letters or minus signs).")
        return None

    return Decimal(text)


def to_rwf(amount):
    """Round a Decimal amount to the nearest whole franc and return a normal whole number."""
    return int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def loan_calculator(request):
    # What the visitor typed, so the boxes keep their values after pressing Calculate
    values = {'amount': '', 'rate': '', 'months': ''}
    errors = []
    result = None

    if request.method == 'POST':
        values['amount'] = request.POST.get('amount', '').strip()
        values['rate'] = request.POST.get('rate', '').strip()
        values['months'] = request.POST.get('months', '').strip()

        # 1. Read and check each box
        amount = read_whole_number(values['amount'], 'Loan amount', errors, required=True)
        rate = read_rate(values['rate'], 'Yearly interest rate', errors)
        months = read_whole_number(values['months'], 'Loan length in months', errors, required=True)

        # 2. Check the limits
        if amount == 0:
            errors.append("Loan amount must be more than 0.")
        if months == 0:
            errors.append("Loan length must be at least 1 month.")
        if months is not None and months > 360:
            errors.append("Please use 360 months (30 years) or less.")
        if rate is not None and rate > 100:
            errors.append("Yearly interest rate must be 100% or less.")

        # 3. If everything is fine, do the maths
        if not errors:
            # Decimal is safer than normal decimals for money maths (no tiny rounding surprises)
            r = rate / Decimal(1200)        # monthly rate: yearly % / 12 months / 100

            if r == 0:
                payment = Decimal(amount) / months      # 0% interest: just split the loan equally
            else:
                # Standard loan formula:  payment = P * r / (1 - (1 + r) ** -n)
                payment = Decimal(amount) * r / (1 - (1 + r) ** -months)

            # Build the repayment table, one row per month
            balance = Decimal(amount)       # how much is still owed
            rows = []
            for month in range(1, months + 1):
                interest = balance * r              # interest is charged on what is still owed
                principal = payment - interest      # the rest of the payment pays off the loan
                balance = balance - principal
                if month == months:
                    balance = Decimal(0)            # remove tiny leftover from rounding
                rows.append({
                    'month': month,
                    'payment': to_rwf(payment),
                    'interest': to_rwf(interest),
                    'principal': to_rwf(principal),
                    'balance': to_rwf(balance),
                })

            total_paid = payment * months
            total_interest = total_paid - amount

            result = {
                'amount': amount,
                'months': months,
                'monthly_payment': to_rwf(payment),
                'total_paid': to_rwf(total_paid),
                'total_interest': to_rwf(total_interest),
                'interest_share': to_rwf(total_interest * 100 / total_paid),   # % of what you pay that is interest
                'rows': rows,
            }

    return render(request, 'main/project_loan_calculator.html', {
        'values': values,
        'errors': errors,
        'result': result,
    })


def projects(request):
    projects = [
        {
            'icon': '🌐',
            'title': 'Personal Portfolio Website',
            'description': 'This site: a multi-page portfolio built with Django and deployed on Render with automatic updates from GitHub.',
            'tech': ['Python', 'Django', 'HTML/CSS', 'Render'],
            'live': 'https://wayne-portfolio-bo8z.onrender.com',
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
        {
            'icon': '💰',
            'title': 'Savings Goal Calculator',
            'description': 'Enter a target in RWF and either what you save each month or how many months you have. It works out the rest. For learning, not financial advice.',
            'tech': ['Python', 'Django', 'Fintech'],
            'page': 'savings_goal',     # opens the demo page on this site
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
        {
            'icon': '🏦',
            'title': 'Loan and Interest Calculator',
            'description': 'Enter a loan amount, a yearly interest rate and a length in months. See the monthly payment, the total interest and a month-by-month repayment table. For learning, not financial advice.',
            'tech': ['Python', 'Django', 'Fintech'],
            'page': 'loan_calculator',   # opens the demo page on this site
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
    ]
    return render(request, 'main/projects.html', {'projects': projects})