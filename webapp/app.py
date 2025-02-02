from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
import bcrypt
import pandas as pd
import json

# --------SETUP FLASK & MONGODB--------
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

load_dotenv()  # load .env file
app = Flask(__name__)
app.secret_key = "this_is_my_random_secret_key_987654321"
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://huangemily449:gourmate101@cluster0.yja9n.mongodb.net/Gourmate?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true"
)


MONGO_DBNAME = os.getenv("MONGO_DBNAME", "Gourmate")

# Connect to MongoDB
client = MongoClient(MONGO_URI)  # create MongoDB client
db = client[MONGO_DBNAME]  # access database
users_collection = db["users"]  # collection of users
rests_collection = db["events"]  # collection of bars

# --------ACCOUNT PAGE--------
@app.route("/account")
def account():
    return render_template("account.html")  # link to account.html

# # --------LOGIN PAGE--------


#     return render_template("login.html") # link to login.html
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        raw_password = request.form["password"].strip()

        # Encode the entered password to bytes
        password_bytes = raw_password.encode("utf-8")

        # Find the user in the database
        user = users_collection.find_one({"username": username})

        if user and "password" in user:
            # user["password"] should be the hashed bytes stored at signup
            stored_hashed_password = user["password"]

            # Check the password using bcrypt
            if bcrypt.checkpw(password_bytes, stored_hashed_password):
                # Password matches, log the user in
                session["user_id"] = str(user["_id"])
                session["username"] = username
                session.permanent = False
                return redirect(url_for("index"))
            else:
                # Incorrect password
                flash("Invalid username or password.", "error")
                return redirect(url_for("login"))
        else:
            # User not found
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

    # GET request just renders the login template
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        raw_password = request.form["password"].strip()

        # Encode the password to bytes
        password_bytes = raw_password.encode("utf-8")
        # Check if username already exists
        if users_collection.find_one({"username": username}):
            flash("Username already exists. Please choose a different one.", "error")
            return redirect(url_for("signup"))

        # Hash the password (bcrypt.hashpw returns bytes)
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        users_collection.insert_one({"username": username, "password": hashed_password})

        flash("Account created successfully. Please log in.", "success")

        # Redirect to login page after successful signup
        return redirect(url_for("login"))

    return render_template("signup.html")



# --------HOME PAGE--------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))  # Redirect to login if the user is not logged in

    # Get user ID from the session
    user_id = session.get("user_id")

    # Fetch restaurant data for the current user from MongoDB
    restaurants = rests_collection.find({"user_id": user_id})  # Query the restaurant collection

    # Convert the MongoDB cursor to a list for rendering in the template
    restaurant_list = list(restaurants)  # Convert the cursor to a list

    # Render the template with the restaurant data
    return render_template("index.html", restaurants=restaurant_list, username=session.get("username"))




# Load data from a file (optional persistent storage)
def load_data():
    try:
        with open('data.json', 'r') as file:
            global data
            data = json.load(file)
    except FileNotFoundError:
        pass

# Save data to a file
def save_data():
    with open('data.json', 'w') as file:
        json.dump(data, file, indent=4)


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

# --------HOME PAGE--------


if __name__ == '__main__':
    load_data()
    app.run(debug=True)
