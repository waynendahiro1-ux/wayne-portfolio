from pathlib import Path
from django.shortcuts import render


def home(request):
    return render(request, 'main/home.html')

def about(request):
    return render(request, 'main/about.html')

def contact(request):
    return render(request, 'main/contact.html')

def story(request):
    return render(request, 'main/story.html')


def basketball(request):
    return render(request, 'main/basketball.html')


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