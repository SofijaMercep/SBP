from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"


def as_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (ValueError, TypeError):
        return None


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    movie_id = 1

    movie = db.ml_movies.find_one({
        "movieId": {"$in": [movie_id, str(movie_id)]}
    })

    link = db.ml_links.find_one({
        "movieId": {"$in": [movie_id, str(movie_id)]}
    })

    print("MovieLens movie:")
    print(movie)
    print()

    print("MovieLens link:")
    print(link)
    print()

    if not link:
        print("Nema link zapisa za ovaj movieId.")
        return

    tmdb_id = as_int(link.get("tmdbId"))

    if tmdb_id is None:
        print("tmdbId nije validan.")
        return

    metadata = db.tmdb_movies_metadata.find_one({"id": tmdb_id})
    credits = db.tmdb_credits.find_one({"id": tmdb_id})
    keywords = db.tmdb_keywords.find_one({"id": tmdb_id})

    print("TMDB metadata:")
    if metadata:
        print({
            "id": metadata.get("id"),
            "title": metadata.get("title"),
            "release_year": metadata.get("release_year"),
            "budget": metadata.get("budget"),
            "revenue": metadata.get("revenue"),
            "popularity": metadata.get("popularity"),
            "genres": metadata.get("genres"),
        })
    else:
        print("Nije pronađen metadata dokument.")
    print()

    print("TMDB credits:")
    if credits:
        print({
            "id": credits.get("id"),
            "first_5_cast": credits.get("cast", [])[:5],
            "directors": credits.get("directors"),
        })
    else:
        print("Nije pronađen credits dokument.")
    print()

    print("TMDB keywords:")
    if keywords:
        print({
            "id": keywords.get("id"),
            "keywords": keywords.get("keywords", [])[:10],
        })
    else:
        print("Nije pronađen keywords dokument.")


if __name__ == "__main__":
    main()