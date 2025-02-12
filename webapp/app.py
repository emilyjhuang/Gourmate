from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests  # Add this line
from datetime import datetime
import os
import bcrypt
import pandas as pd
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import overpy
import time

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
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            data = request.get_json()
            print("Received JSON:", data)

            lat1, lng1 = data.get("lat1"), data.get("lng1")
            lat2, lng2 = data.get("lat2"), data.get("lng2")
            price = data.get("price")
            cuisine = data.get("cuisine")

            if not all([lat1, lng1, lat2, lng2]):
                return jsonify({"error": "Invalid locations"}), 400

            # Find midpoint
            mid_lat, mid_lng = (float(lat1) + float(lat2)) / 2, (float(lng1) + float(lng2)) / 2

            # Fetch restaurants using Overpass API
            restaurants = get_restaurants(mid_lat, mid_lng, price, cuisine)

            return render_template("results.html", restaurants=restaurants, mid_lat=mid_lat, mid_lng=mid_lng)
        
        except Exception as e:
            print("Error processing request:", e)
            return jsonify({"error": "An error occurred while processing your request. Please try again."}), 500

    return render_template("index.html")


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


def get_restaurants(mid_lat, mid_lng, price, cuisine):
    """Fetch restaurant recommendations using Overpass API (OpenStreetMap)."""
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json];
    node
      ["amenity"="restaurant"]
      (around:2000,{mid_lat},{mid_lng});
    out;
    """

    try:
        response = requests.get(overpass_url, params={"data": query}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching data from Overpass API:", e)
        return []

    restaurants = []
    for element in data.get("elements", []):
        name = element.get("tags", {}).get("name", "Unknown")
        address = element.get("tags", {}).get("addr:street", "No address provided")
        cuisine_type = element.get("tags", {}).get("cuisine", "Unknown").lower()
        lat, lon = element.get("lat"), element.get("lon")

        if cuisine and cuisine.lower() not in cuisine_type:
            continue

        if price and price not in ["$", "$$", "$$$"]:
            continue  

        restaurants.append({
            "name": name,
            "address": address,
            "cuisine": cuisine_type.capitalize(),
            "lat": lat,
            "lon": lon
        })

    return restaurants



@app.route("/myrestaurants")
def my_restaurants():
    return render_template("myrestaurants.html")

@app.route("/results", methods=["POST", "GET"])
def results():
    if request.method == "POST":
        try:
            data = request.get_json()
            print("Received JSON:", data)

            lat1, lng1 = data.get("lat1"), data.get("lng1")
            lat2, lng2 = data.get("lat2"), data.get("lng2")
            price = data.get("price")
            cuisine = data.get("cuisine")

            if not all([lat1, lng1, lat2, lng2]):
                return jsonify({"error": "Invalid locations"}), 400

            # Find midpoint
            mid_lat, mid_lng = (float(lat1) + float(lat2)) / 2, (float(lng1) + float(lng2)) / 2

            # Fetch restaurants using Overpass API
            restaurants = get_restaurants(mid_lat, mid_lng, price, cuisine)

            return jsonify({"mid_lat": mid_lat, "mid_lng": mid_lng, "restaurants": restaurants})

        except Exception as e:
            print("Error processing request:", e)
            return jsonify({"error": "An error occurred while processing your request. Please try again."}), 500

    elif request.method == "GET":
        # Get midpoint values from query parameters
        mid_lat = request.args.get("mid_lat")
        mid_lng = request.args.get("mid_lng")

        # Ensure values are valid
        if not mid_lat or not mid_lng:
            return "Invalid request", 400

        return render_template("results.html", mid_lat=mid_lat, mid_lng=mid_lng)

@app.route('/restaurant_results')
def restaurant_results():
    # Get locations from session
    location1_name = session.get('location1_name')
    location2_name = session.get('location2_name')
    
    if not location1_name or not location2_name:
        flash("Please enter two locations first", "error")
        return redirect(url_for('index'))
    
    # Get restaurant data
    result = find_restaurants_between_locations(location1_name, location2_name)
    
    if not result['success']:
        flash(result['error'], "error")
        return redirect(url_for('index'))
    
    # Prepare the data for JSON serialization
    restaurant_data = result['restaurants']  # This is already a list of dictionaries
    location_data = {
        'location1': {
            'name': location1_name,
            'lat': float(result['locations']['location1']['lat']),
            'lng': float(result['locations']['location1']['lon'])
        },
        'location2': {
            'name': location2_name,
            'lat': float(result['locations']['location2']['lat']),
            'lng': float(result['locations']['location2']['lon'])
        }
    }
    
    # Convert any non-serializable values to strings
    for restaurant in restaurant_data:
        for key, value in restaurant.items():
            if not isinstance(value, (str, int, float, bool, type(None))):
                restaurant[key] = str(value)
    
    return render_template(
        'restaurant_results.html',
        restaurants=restaurant_data,
        location1=location_data['location1'],
        location2=location_data['location2']
    )

@app.route("/profile")
def profile():
    return render_template("profile.html")

def get_coordinates(location):
    """Convert location name to latitude & longitude using OpenStreetMap."""
    geolocator = Nominatim(user_agent="restaurant_finder_app")
    try:
        time.sleep(1)  # Respect rate limits
        location_data = geolocator.geocode(location)
        if location_data:
            return {
                'lat': location_data.latitude,
                'lon': location_data.longitude,
                'name': location,
                'address': location_data.address
            }
        return None
    except Exception as e:
        print(f"Error geocoding {location}: {e}")
        return None

def find_midpoint(loc1, loc2):
    """Find geographic midpoint between two locations."""
    return {
        'lat': (loc1['lat'] + loc2['lat']) / 2,
        'lon': (loc1['lon'] + loc2['lon']) / 2
    }

def search_restaurants(midpoint, radius=1000):
    """Search for restaurants near the midpoint using OpenStreetMap."""
    api = overpy.Overpass()
    
    query = f"""
    [out:json][timeout:25];
    (
        node["amenity"="restaurant"](around:{radius},{midpoint['lat']},{midpoint['lon']});
        way["amenity"="restaurant"](around:{radius},{midpoint['lat']},{midpoint['lon']});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        result = api.query(query)
        restaurants = []
        
        for node in result.nodes:
            restaurant_location = (float(node.lat), float(node.lon))
            midpoint_location = (midpoint['lat'], midpoint['lon'])
            
            restaurant = {
                'name': node.tags.get('name', 'Unknown Restaurant'),
                'lat': float(node.lat),
                'lon': float(node.lon),
                'cuisine': node.tags.get('cuisine', 'Not specified'),
                'address': f"{node.tags.get('addr:street', '')} {node.tags.get('addr:housenumber', '')}".strip() or 'Address not available',
                'distance': round(geodesic(midpoint_location, restaurant_location).meters),
                'phone': node.tags.get('phone', 'Not available'),
                'website': node.tags.get('website', ''),
                'opening_hours': node.tags.get('opening_hours', 'Hours not specified')
            }
            restaurants.append(restaurant)
        
        # Sort by distance from midpoint
        restaurants.sort(key=lambda x: x['distance'])
        return restaurants
        
    except Exception as e:
        print(f"Error querying OpenStreetMap: {e}")
        return []

def find_restaurants_between_locations(location1, location2, radius=1000):
    """Find restaurants between two locations."""
    # Get coordinates and location details
    loc1_data = get_coordinates(location1)
    loc2_data = get_coordinates(location2)
    
    if not (loc1_data and loc2_data):
        print(f"Could not find coordinates for one or both locations: {location1}, {location2}")
        return {
            'success': False,
            'error': 'Could not find one or both locations',
            'restaurants': [],
            'locations': None
        }
    
    # Calculate midpoint
    midpoint = find_midpoint(loc1_data, loc2_data)
    
    # Calculate actual distance between points to adjust search radius if needed
    distance = geodesic(
        (loc1_data['lat'], loc1_data['lon']),
        (loc2_data['lat'], loc2_data['lon'])
    ).meters
    
    # Adjust radius if distance between points is larger than default radius
    search_radius = max(radius, distance / 2)
    
    # Search for restaurants
    restaurants = search_restaurants(midpoint, search_radius)
    
    return {
        'success': True,
        'restaurants': restaurants,
        'locations': {
            'location1': loc1_data,
            'location2': loc2_data,
            'midpoint': midpoint
        },
        'search_radius': search_radius
    }


if __name__ == "__main__":
    app.run(debug=True)

