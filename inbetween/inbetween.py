import googlemaps
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# Your Google API Key (store securely in a .env file in production)
GOOGLE_API_KEY = "AIzaSyBI6hMOZ_ntJpd4UZXFZmLZgOmR8O0eb1A"
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)
geolocator = Nominatim(user_agent="location_finder")

# Initialize Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)
geolocator = Nominatim(user_agent="location_finder")

def get_coordinates(location):
    """Convert location name to latitude & longitude."""
    location_data = geolocator.geocode(location)
    if location_data:
        return (location_data.latitude, location_data.longitude)
    return None

def find_midpoint(loc1, loc2):
    """Find geographic midpoint between two locations."""
    lat1, lon1 = loc1
    lat2, lon2 = loc2
    return ((lat1 + lat2) / 2, (lon1 + lon2) / 2)

def search_restaurants(midpoint, radius=1000):
    """Search for restaurants near the midpoint using Google Places API."""
    places = gmaps.places_nearby(
        location=midpoint,
        radius=radius,
        type="restaurant"
    )
    
    restaurants = []
    if "results" in places:
        for place in places["results"][:10]:  # Limit to top 10 results
            restaurants.append({
                "name": place["name"],
                "address": place["vicinity"],
                "rating": place.get("rating", "No rating"),
                "location": place["geometry"]["location"]
            })
    return restaurants

# Example usage
loc1 = input("Enter first location: ")
loc2 = input("Enter second location: ")

coord1 = get_coordinates(loc1)
coord2 = get_coordinates(loc2)

if coord1 and coord2:
    midpoint = find_midpoint(coord1, coord2)
    print(f"Midpoint Coordinates: {midpoint}")

    restaurants = search_restaurants(midpoint)
    
    print("\nTop Restaurant Recommendations:")
    for i, r in enumerate(restaurants, 1):
        print(f"{i}. {r['name']} - {r['address']} (Rating: {r['rating']})")
else:
    print("Could not find coordinates for one or both locations.")
