# TaskFlow AI

A simple task manager web app built with **Flask** and **SQLite**. Users can sign up, log in, and manage their daily tasks.

## Features

- Sign up, login, and logout
- Add, view, edit, and delete tasks
- Mark tasks as done
- Task details page
- Profile page with photo upload
- Export tasks to CSV

## Tech Stack

- Python 3.10
- Flask
- Flask-SQLAlchemy (SQLite)
- HTML, CSS (Jinja2 templates)

## How to Run

1. Clone the repo:

   ```bash
   git clone https://github.com/YOUR-USERNAME/taskflow-ai.git
   cd taskflow-ai
   ```

2. Install the requirements:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   python app.py
   ```

4. Open in your browser: **http://127.0.0.1:5000**

The database (`taskflow.db`) is created automatically on the first run.

## Project Structure

```
taskflow-ai/
├── app.py
├── requirements.txt
├── templates/
└── static/
```

## Team

- Lanip, Francheska
- Padilla, Dionard
- Baldoza, Anthony
- Cervantes, Chrissa