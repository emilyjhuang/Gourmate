from collections import Counter
from pymongo import MongoClient

import os
from dotenv import load_dotenv
from bson.objectid import ObjectId

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME")

client = MongoClient(MONGO_URI)
db = client[MONGO_DBNAME]
users = db.users
restaurants = db.restaurants
ratings = db.ratings

from bson.objectid import ObjectId

def generate_user_profile(user_id):
    cuisine_count = {}
    total_rating = 0
    rating_count = 0
    price_levels = []

    visited = ratings.find({'user_id': user_id})

    for entry in visited:
        try:
            rest_id = entry.get('restaurant_id')
            if not rest_id:
                continue
            rest = restaurants.find_one({'_id': ObjectId(rest_id)})
            if not rest:
                continue

            # Cuisine
            cuisine = rest.get('cuisine')
            if cuisine:
                cuisine_count[cuisine] = cuisine_count.get(cuisine, 0) + 1

            # Price level (e.g. "$$" -> 2)
            price = rest.get('price')
            if price:
                price_levels.append(len(price))

            # Rating
            user_rating = entry.get('user_rating')
            if user_rating:
                total_rating += float(user_rating)
                rating_count += 1

        except Exception as e:
            print(f"Skipping bad entry: {e}")
            continue

    avg_rating = total_rating / rating_count if rating_count > 0 else 0
    avg_price = sum(price_levels) / len(price_levels) if price_levels else 2

    return {
        'preferred_cuisines': sorted(cuisine_count, key=cuisine_count.get, reverse=True)[:3],
        'avg_rating': avg_rating,
        'avg_price_level': avg_price
    }


def recommend_restaurants(user_id, limit=5):
    profile = generate_user_profile(user_id)
    print("PROFILE:", profile)

    query = {}

    # Only include cuisine filter if available
    if profile['preferred_cuisines']:
        query['cuisine'] = {'$in': profile['preferred_cuisines']}

    # Always filter by rating
    query['rating'] = {'$gte': max(profile['avg_rating'] - 0.5, 3)}  # don't go too low

    # Match price level as "$", "$$", etc.
    price_str = '$' * round(profile.get('avg_price_level', 2))
    query['price'] = price_str

    # Exclude already visited
    visited_ids = ratings.find({'user_id': user_id})
    visited_rest_ids = [ObjectId(r['restaurant_id']) for r in visited_ids if 'restaurant_id' in r]
    if visited_rest_ids:
        query['_id'] = {'$nin': visited_rest_ids}

    print("QUERY:", query)

    return list(restaurants.find(query).sort('rating', -1).limit(limit))