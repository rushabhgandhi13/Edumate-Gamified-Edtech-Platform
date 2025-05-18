# Edumate

EduMate is a gamified EdTech web application designed to enhance learning engagement 
and retention through AI-driven personalization and game mechanics. The platform 
addresses the challenges of passive learning by integrating elements such as points, 
badges, leaderboards, and adaptive learning insights, ensuring a highly interactive 
and motivating educational experience.

## Features

### For Students

- **Course Enrollment**: Browse and enroll in a variety of courses across different categories.
- **Interactive Learning**: Access lessons, videos, and quizzes for each course.
- **Progress Tracking**: Monitor your learning progress through courses and modules.
- **Personalized Quizzes**: Take specially generated quizzes based on your weak areas to improve learning outcomes.
- **Study Planning**: Create and manage study sessions with a built-in calendar interface.
- **Learning Path**: View a personalized learning path with recommended courses.
- **Deadlines & Goals**: Set and track learning goals and deadlines.
- **Gamification**: Earn points and achievements as you progress through courses.

### For Instructors

- **Course Management**: Create and manage courses with detailed information.
- **Module Creation**: Organize course content into modules with different types of materials.
- **Content Development**: Add lessons, videos, and quizzes to modules.
- **Quiz Builder**: Create comprehensive quizzes with various question types.
- **Student Progress**: Monitor student enrollment and progress in your courses.

## Technologies

- **Backend**: Python with Django framework
- **Frontend**: HTML, CSS, JavaScript, Bootstrap etc.
- **Database**: SQLite (development) 

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- virtualenv (recommended)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/rushabhnixen/edumate.git
   cd edumate
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure the database:
   ```
   python manage.py migrate
   ```

5. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```
   python manage.py runserver
   ```

7. Access the application at http://127.0.0.1:8000/

## Usage

### Student Account

1. Register a new account or log in
2. Browse available courses and enroll
3. Access course materials and track your progress
4. Take quizzes to test your knowledge
5. Set up your study schedule and learning goals
6. Earn points and achievements as you learn

### Instructor Account

1. Log in with an instructor account
2. Create new courses with detailed information
3. Add modules to your courses
4. Create lessons, upload videos, and design quizzes
5. Monitor student enrollment and progress

## Project Structure

- **accounts/**: User authentication and profile management
- **courses/**: Core course management functionality
- **gamification/**: Points, achievements, and badges system
- **static/**: CSS, JavaScript, and images
- **templates/**: HTML templates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.