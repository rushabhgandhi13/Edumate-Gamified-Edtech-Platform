#!/usr/bin/env python
import os
import secrets
import shutil
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent

def create_env_file():
    """Create a .env file from .env.example if it doesn't exist"""
    if not os.path.exists(os.path.join(BASE_DIR, '.env')):
        print("Creating .env file from .env.example...")
        
        # Check if .env.example exists
        if os.path.exists(os.path.join(BASE_DIR, '.env.example')):
            with open(os.path.join(BASE_DIR, '.env.example'), 'r') as example_file:
                env_content = example_file.read()
            
            # Generate a new secret key
            secret_key = secrets.token_urlsafe(50)
            env_content = env_content.replace('your_unique_secret_key_here', secret_key)
            
            with open(os.path.join(BASE_DIR, '.env'), 'w') as env_file:
                env_file.write(env_content)
            
            print("✅ .env file created successfully!")
        else:
            print("❌ .env.example file not found. Please create a .env file manually.")
    else:
        print("✅ .env file already exists.")

def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        os.path.join(BASE_DIR, 'media'),
        os.path.join(BASE_DIR, 'static'),
        os.path.join(BASE_DIR, 'static', 'css'),
        os.path.join(BASE_DIR, 'static', 'js'),
        os.path.join(BASE_DIR, 'static', 'images'),
        os.path.join(BASE_DIR, 'templates'),
        os.path.join(BASE_DIR, 'templates', 'accounts'),
        os.path.join(BASE_DIR, 'templates', 'courses'),
        os.path.join(BASE_DIR, 'templates', 'gamification'),
        os.path.join(BASE_DIR, 'templates', 'analytics'),
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory already exists: {directory}")

def run_migrations():
    """Run Django migrations"""
    print("\nRunning migrations...")
    os.system('python manage.py migrate')

def create_superuser():
    """Prompt to create a superuser"""
    print("\nDo you want to create a superuser? (y/n)")
    choice = input().lower()
    if choice == 'y':
        os.system('python manage.py createsuperuser')

def collect_static():
    """Prompt to collect static files"""
    print("\nDo you want to collect static files? (y/n)")
    choice = input().lower()
    if choice == 'y':
        os.system('python manage.py collectstatic --noinput')

def main():
    """Main setup function"""
    print("🚀 Setting up EduMate project...\n")
    
    create_env_file()
    create_directories()
    run_migrations()
    create_superuser()
    collect_static()
    
    print("\n✨ Setup complete! ✨")
    print("\nTo run the development server:")
    print("python manage.py runserver")
    print("\nAccess the admin interface at:")
    print("http://127.0.0.1:8000/admin/")
    print("\nAccess the main site at:")
    print("http://127.0.0.1:8000/")

if __name__ == "__main__":
    main() 