from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta
import calendar
import requests
import os

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = 'secret'

# Bcrypt setup
bcrypt = Bcrypt(app)

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client.taskdb
tasks_collection = db.tasks
ai_tasks_collection = db.ai_tasks

# GROQ AI task generation
def generate_ai_tasks(prompt):
    try:
        api_key = os.getenv("GROQ_API_KEY")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that creates to-do task lists."},
                {"role": "user", "content": f"Make a short to-do list for: {prompt}"}
            ]
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as err:
        print(f"[GROQ ERROR] {err}")
        raise

# Routes

@app.route("/")
def index():
    tasks = list(tasks_collection.find())
    return render_template("index.html", tasks=tasks)

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        task = {
            "task": request.form["task"],
            "priority": request.form["priority"],
            "deadline": request.form["deadline"],
            "category": request.form["category"],
            "completed": False
        }
        tasks_collection.insert_one(task)
        return redirect(url_for("index"))
    return render_template("add.html")

@app.route("/delete/<task_id>")
def delete(task_id):
    tasks_collection.delete_one({"_id": ObjectId(task_id)})
    return redirect(url_for("index"))

@app.route("/complete/<task_id>")
def complete_task(task_id):
    tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"completed": True}})
    return redirect(url_for("index"))

@app.route("/generate", methods=["GET", "POST"])
def generate():
    if request.method == "POST":
        prompt = request.form.get("prompt")
        if not prompt:
            flash("Please enter a prompt.")
            return redirect(url_for("generate"))

        try:
            tasks_text = generate_ai_tasks(prompt)
            ai_tasks_collection.insert_one({
                "prompt": prompt,
                "response": tasks_text
            })
            flash("AI tasks generated successfully.")
        except Exception as e:
            flash(f"GROQ Error: {str(e)}")

        return redirect(url_for("ai_results"))

    return render_template("generate.html")

@app.route("/ai-results")
def ai_results():
    results = list(ai_tasks_collection.find())
    return render_template("ai_results.html", results=results)

@app.route("/add-ai-task", methods=["POST"])
def add_ai_task():
    task_text = request.form.get("task_text")
    if task_text:
        task = {
            "task": task_text,
            "priority": "medium",
            "deadline": datetime.today().strftime("%Y-%m-%d"),
            "category": "ai",
            "completed": False
        }
        tasks_collection.insert_one(task)
        flash("Task added successfully.")
    return redirect(url_for("ai_results"))

@app.route("/delete-ai-result/<result_id>", methods=["POST"])
def delete_ai_result(result_id):
    ai_tasks_collection.delete_one({"_id": ObjectId(result_id)})
    flash("AI task entry deleted.")
    return redirect(url_for("ai_results"))

@app.route("/daily")
def daily():
    daily_tasks = list(tasks_collection.find({"category": "daily"}))
    return render_template("daily.html", tasks=daily_tasks)

@app.route("/weekly")
def weekly_tasks():
    all_tasks = tasks_collection.find()
    tasks_by_date = defaultdict(list)

    for task in all_tasks:
        if "deadline" in task:
            try:
                date_obj = datetime.strptime(task["deadline"], "%Y-%m-%d")
                tasks_by_date[date_obj.date()].append(task)
            except ValueError:
                continue

    today = datetime.today()
    monday = today - timedelta(days=today.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    week_schedule = []
    for date in week_dates:
        day_name = calendar.day_name[date.weekday()]
        display_str = date.strftime("%b %d, %Y")
        day_tasks = tasks_by_date.get(date.date(), [])
        week_schedule.append((day_name, display_str, day_tasks))

    return render_template("weekly.html", week_schedule=week_schedule)

# ✅ Only one __main__ block for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Required for Render
    app.run(debug=False, host='0.0.0.0', port=port)




