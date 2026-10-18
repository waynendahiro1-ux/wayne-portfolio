import json
import logging
import urllib.error
import urllib.request
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
    ]
    return render(request, 'main/projects.html', {'projects': projects})