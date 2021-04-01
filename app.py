import os
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for, Markup)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")


mongo = PyMongo(app)


@app.route("/")
@app.route("/get_tasks")
def get_tasks():
    tasks = list(mongo.db.tasks.find())
    return render_template("tasks.html", tasks=tasks)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # check if username already exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))

        register = {
            "username": request.form.get("username").lower(),
            "password": generate_password_hash(request.form.get("password"))
        }
        mongo.db.users.insert_one(register)

        # put the new user into 'session' cookie
        session["user"] = request.form.get("username").lower()
        flash("registration successful!")
        return redirect(url_for("profile", username=session["user"]))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # check if username exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        if existing_user:
            # ensure hashed password matches user input
            if check_password_hash(existing_user["password"], request.form.get("password")):
                session["user"] = request.form.get("username").lower()
                flash("Welcome, {}".format(request.form.get("username")))
                return redirect(url_for("profile", username=session["user"]))
            else:
                # invalid password match
                flash("Incorrect Username and/or Password")
                return redirect(url_for("login"))
        else:
            # username doesn't exist
            flash("Incorrect Username")
            return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    # grab the sessions user's username from db
    if session.get("user"):
        username = mongo.db.users.find_one(
            {"username": session["user"]})["username"]
        return render_template("profile.html", username=username)

    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    if session.get("user"):
        # remove user from session cookies
        session.pop("user")

    flash("You have been logged out")
    return redirect(url_for("login"))


@app.route("/add_task", methods=["GET", "POST"])
def add_task():
    if not session.get("user"):
        return redirect(url_for("login"))

    if request.method == "POST":
        is_urgent = "on" if request.form.get("is_urgent") else "off"
        task = {
            "category_name": request.form.get("category_name"),
            "task_name": request.form.get("task_name"),
            "task_description": request.form.get("task_description"),
            "is_urgent": is_urgent,
            "due_date": request.form.get("due_date"),
            "created_by": session["user"],
            "complete": False
        }
        mongo.db.tasks.insert_one(task)
        flash("Task successfully Added")
        return redirect(url_for("get_tasks"))

    categories = mongo.db.categories.find().sort("category_name", 1)
    return render_template("add_task.html", categories=categories)


@app.route("/edit_task/<task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if not session.get("user"):
        return redirect(url_for("login"))

    if request.method == "POST":
        is_urgent = "on" if request.form.get("is_urgent") else "off"
        submit = {
            "category_name": request.form.get("category_name"),
            "task_name": request.form.get("task_name"),
            "task_description": request.form.get("task_description"),
            "is_urgent": is_urgent,
            "due_date": request.form.get("due_date"),
            "created_by": session["user"]
        }
        mongo.db.tasks.update({"_id": ObjectId(task_id)}, {
                              "$set": submit})
        flash("Task successfully Updated")

    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    categories = mongo.db.categories.find().sort("category_name", 1)

    if task['created_by'] != session["user"]:
        flash("You can't edit a task that's not created by you!")
        return redirect(url_for("get_tasks"))

    return render_template("edit_task.html", task=task, categories=categories)


@app.route("/complete_task/<task_id>")
def complete_task(task_id):
    if not session.get("user"):
        return redirect(url_for("login"))

    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    if task['created_by'] != session["user"]:
        flash("You can't complete a task that's not created by you!")
    else:
        flash(
            Markup("Task <u>{}</u> was successfully completed".format(task['task_name'])))
        mongo.db.tasks.update({"_id": ObjectId(task_id)}, {
                              "$set": {"complete": True}})

    return redirect(url_for("get_tasks"))


@app.route("/get_categories")
def get_categories():
    if session.get("user") and session["user"].lower() == "admin".lower():
        categories = list(mongo.db.categories.find().sort("category_name", 1))
        return render_template("categories.html", categories=categories)
    elif session.get("user"):
        flash("You don't have the user privileges to access this section")
        return redirect(url_for("get_tasks"))

    return redirect(url_for("login"))


@app.route('/add_category', methods=["GET", "POST"])
def add_category():
    if session.get("user") and session["user"].lower() == "admin".lower():
        if request.method == "POST":
            category = {
                "category_name": request.form.get("category_name"),
            }
            mongo.db.categories.insert_one(category)
            flash(Markup(
                "Category <strong>{}</strong> successfully Added".format(category['category_name'])))
            return redirect(url_for("get_categories"))

        return render_template("add_category.html")
    elif session.get("user"):
        flash("You don't have the user privileges to access this section")
        return redirect(url_for("get_tasks"))

    return redirect(url_for("login"))


@app.route('/edit_category/<category_id>', methods=["GET", "POST"])
def edit_category(category_id):
    if session.get("user") and session["user"].lower() == "admin".lower():
        category = mongo.db.categories.find_one({"_id": ObjectId(category_id)})
        if request.method == "POST":
            submit = {
                "category_name": request.form.get("category_name"),
            }
            mongo.db.categories.update(
                {"_id": ObjectId(category_id)}, {"$set": submit})
            flash(Markup(
                "Category name successfully changed:<br> <strike>{0}</strike> > <strong>{1}</strong>".format(category['category_name'], submit["category_name"])))
            return redirect(url_for("get_categories"))

        return render_template("edit_category.html", category=category)
    elif session.get("user"):
        flash("You don't have the user privileges to access this section")
        return redirect(url_for("get_tasks"))

    return redirect(url_for("login"))


@app.route('/delete_category/<category_id>')
def delete_category(category_id):
    if session.get("user") and session["user"].lower() == "admin".lower():
        mongo.db.categories.remove({"_id": ObjectId(category_id)})
        flash("Category was successfully deleted")
        return redirect(url_for("get_categories"))
    elif session.get("user"):
        flash("You don't have the user privileges to access this section")
        return redirect(url_for("get_tasks"))

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
