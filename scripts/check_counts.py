from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"

collections = [
    "ml_movies",
    "ml_links",
    "ml_ratings",
    "ml_tags",
    "ml_genome_tags",
    "ml_genome_scores",
    "tmdb_movies_metadata",
    "tmdb_credits",
    "tmdb_keywords",
]


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print(f"Baza: {DB_NAME}")
    print("-" * 50)

    for collection_name in collections:
        count = db[collection_name].count_documents({})
        print(f"{collection_name}: {count}")


if __name__ == "__main__":
    main()