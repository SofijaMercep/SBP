from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
USER_ID = 123


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    high_ratings = list(db.ml_ratings.find(
        {
            "userId": USER_ID,
            "rating": {"$gte": 4.5}
        },
        {
            "_id": 0,
            "movieId": 1,
            "rating": 1
        }
    ).sort("rating", -1))

    all_ratings_count = db.ml_ratings.count_documents({
        "userId": USER_ID
    })

    print(f"Provjera korisnika userId = {USER_ID}")
    print("=" * 50)
    print(f"Ukupan broj ocjena korisnika: {all_ratings_count}")
    print(f"Broj ocjena 4.5 ili 5.0: {len(high_ratings)}")
    print("")

    if len(high_ratings) < 5:
        print("Korisnik nema najmanje 5 visokih ocjena. Treba izabrati drugog korisnika.")
        return

    movie_ids = [rating["movieId"] for rating in high_ratings[:20]]

    movies = list(db.ml_movies.find(
        {
            "movieId": {"$in": movie_ids}
        },
        {
            "_id": 0,
            "movieId": 1,
            "title": 1,
            "genres": 1
        }
    ))

    movies_by_id = {
        movie["movieId"]: movie
        for movie in movies
    }

    print("Primjeri filmova koje je korisnik visoko ocijenio:")
    print("")

    for rating in high_ratings[:20]:
        movie = movies_by_id.get(rating["movieId"])

        if not movie:
            continue

        print(
            f"- {movie.get('title')} | "
            f"rating: {rating.get('rating')} | "
            f"genres: {movie.get('genres')}"
        )


if __name__ == "__main__":
    main()