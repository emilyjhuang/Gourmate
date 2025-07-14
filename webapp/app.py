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
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

MONGO_URI = os.getenv("MONGO_URI")

MONGO_DBNAME = os.getenv("MONGO_DBNAME", "Gourmate")

#yelp
YELP_API_Key = os.getenv('YELP_API_Key')

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
            radius = int(data.get("radius", 2000))

            if not all([lat1, lng1, lat2, lng2]):
                return jsonify({"error": "Invalid locations"}), 400

            # Find midpoint
            mid_lat, mid_lng = (float(lat1) + float(lat2)) / 2, (float(lng1) + float(lng2)) / 2

            # Fetch restaurants using Overpass API
            restaurants = get_restaurants(mid_lat, mid_lng, price, cuisine, radius)
            print("Yelp API response data:", json.dumps(data, indent=2))


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


def get_restaurants(mid_lat, mid_lng, price=None, cuisine=None, radius=2000):
    url = "https://api.yelp.com/v3/businesses/search"
    headers = { "Authorization": f"Bearer {YELP_API_Key}"}

    params = {
        "latitude": mid_lat,
        "longitude": mid_lng,
        "categories": "restaurants",
        "radius": radius,
        "limit": 20,
        "sort_by": "best_match"
    }

    if price:
        params["price"] = price

    if cuisine and cuisine.strip():
        params["categories"] = cuisine.strip().lower() 
    else:
        params["categories"] = "restaurants"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout = 10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching data from API:", e)
        return []
    
    restaurants = []
    for biz in data.get("businesses", []):
        restaurants.append({
            "name": biz.get("name", "Unknown"),
            "address": ", ".join(biz.get("location", {}).get("display_address", [])),
            "categories": ", ".join([c["title"] for c in biz.get("categories", [])]),
            "lat": biz.get("coordinates", {}).get("latitude"),
            "lon": biz.get("coordinates", {}).get("longitude"),
            "price": biz.get("price", "N/A"),
            "rating": biz.get("rating", "N/A"),
            "url": biz.get("url", "")
        })
    return restaurants


@app.route("/myrestaurants")
def my_restaurants():
    if 'user_id' not in session:
        flash("Please log in to view your saved restaurants.", "error")
        return redirect(url_for('login'))

    saved_restaurants = list(db.saved_restaurants.find({"user_id": session['user_id']}))
    return render_template("myrestaurants.html", saved_restaurants=saved_restaurants)


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
            radius = int(data.get("radius", 2000))
        
            # Validate and convert coordinates
            try:
                lat1, lng1 = float(lat1), float(lng1)
                lat2, lng2 = float(lat2), float(lng2)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid coordinate values"}), 400

            if not all([lat1, lng1, lat2, lng2]):
                return jsonify({"error": "Invalid locations"}), 400

            mid_lat, mid_lng = (lat1 + lat2) / 2, (lng1 + lng2) / 2

            restaurants = get_restaurants(mid_lat, mid_lng, price, cuisine, radius)

            # Store data in session for GET request - ensure all values are JSON serializable
            session['restaurants'] = restaurants
            session['mid_lat'] = float(mid_lat)
            session['mid_lng'] = float(mid_lng)
            session['location_a'] = {"lat": float(lat1), "lng": float(lng1)}
            session['location_b'] = {"lat": float(lat2), "lng": float(lng2)}

            return jsonify({
                "success": True,
                "redirect_url": f"/results?mid_lat={mid_lat}&mid_lng={mid_lng}"
            })

        except Exception as e:
            print("Error processing request:", e)
            return jsonify({"error": "An error occurred while processing your request. Please try again."}), 500

    elif request.method == "GET":
        # Try to get mid_lat/mid_lng from query params first
        mid_lat_param = request.args.get("mid_lat")
        mid_lng_param = request.args.get("mid_lng")
        
        mid_lat = None
        mid_lng = None
        
        # If query params are valid, use them; otherwise fall back to session
        if mid_lat_param and mid_lng_param and mid_lat_param != 'undefined' and mid_lng_param != 'undefined':
            try:
                mid_lat = float(mid_lat_param)
                mid_lng = float(mid_lng_param)
            except (ValueError, TypeError):
                print(f"Error converting query params to float: {mid_lat_param}, {mid_lng_param}")
                mid_lat = None
                mid_lng = None
        
        # Fall back to session values if query params failed
        if mid_lat is None or mid_lng is None:
            mid_lat = session.get('mid_lat')
            mid_lng = session.get('mid_lng')
            
            # Convert to float if they're strings
            if isinstance(mid_lat, str):
                try:
                    mid_lat = float(mid_lat)
                except (ValueError, TypeError):
                    mid_lat = None
                    
            if isinstance(mid_lng, str):
                try:
                    mid_lng = float(mid_lng)
                except (ValueError, TypeError):
                    mid_lng = None

        # Get other data from session with proper defaults
        restaurants = session.get('restaurants', [])
        location_a = session.get('location_a')
        location_b = session.get('location_b')

        # Ensure location_a and location_b are valid dictionaries
        if not isinstance(location_a, dict) or 'lat' not in location_a or 'lng' not in location_a:
            location_a = {"lat": mid_lat or 0.0, "lng": mid_lng or 0.0}
        
        if not isinstance(location_b, dict) or 'lat' not in location_b or 'lng' not in location_b:
            location_b = {"lat": mid_lat or 0.0, "lng": mid_lng or 0.0}

        # If we still don't have valid coordinates, redirect to home
        if not mid_lat or not mid_lng or mid_lat == 0.0 and mid_lng == 0.0:
            flash("Please enter two locations first", "error")
            return redirect(url_for('index'))

        # Ensure all values are JSON serializable
        return render_template(
            "results.html",
            restaurants=restaurants if isinstance(restaurants, list) else [],
            mid_lat=float(mid_lat),
            mid_lng=float(mid_lng),
            location1=location_a,
            location2=location_b
        )

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

@app.route('/save-restaurant', methods=['POST'])
def save_restaurant():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'User not logged in'}), 401
    
    try:
        data = request.get_json()
        restaurant_data = {
            'user_id': session['user_id'],
            'name': data.get('name'),
            'address': data.get('address'),
            'cuisine': data.get('cuisine'),
            'price': data.get('price'),
            'rating': data.get('rating'),
            'url': data.get('url'),
            'saved_at': datetime.now()
        }
        
        # Check if restaurant is already saved by this user
        existing = db.saved_restaurants.find_one({
            'user_id': session['user_id'],
            'name': restaurant_data['name'],
            'address': restaurant_data['address']
        })
        
        if existing:
            return jsonify({'success': False, 'error': 'Restaurant already saved'}), 400
        
        # Save to database
        db.saved_restaurants.insert_one(restaurant_data)
        
        return jsonify({'success': True, 'message': 'Restaurant saved successfully'})
        
    except Exception as e:
        print(f"Error saving restaurant: {e}")
        return jsonify({'success': False, 'error': 'Failed to save restaurant'}), 500


if __name__ == "__main__":
    app.run(debug=True)

