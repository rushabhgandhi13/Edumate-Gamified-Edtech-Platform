from django.shortcuts import render, redirect
from django.views.generic import TemplateView

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().get(request, *args, **kwargs) 