from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    search_words = ["dark", "psychological", "twist", "mind", "bending"]

    print("Provjera genome tagova")
    print("=" * 50)

    for word in search_words:
        print(f"\nTagovi koji sadrze: {word}")
        results = list(db.ml_genome_tags.find(
            {"tag": {"$regex": word, "$options": "i"}},
            {"_id": 0, "tagId": 1, "tag": 1}
        ).sort("tag", 1))

        if not results:
            print("  Nema rezultata.")
            continue

        for tag in results:
            print(f"  tagId={tag.get('tagId')}, tag={tag.get('tag')}")


if __name__ == "__main__":
    main()