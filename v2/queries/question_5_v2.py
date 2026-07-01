from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
USER_ID = 123
OUTPUT_FILE = Path("v2/results/question_5_v2_results.txt")

MIN_AVG_RATING = 4.0
MIN_RATING_COUNT = 1000


def round_number(value, decimals=3):
    if value is None:
        return None

    return round(value, decimals)


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v2 upit za pitanje 5...")
    print("Upit se izvrsava nad novom reorganizovanom kolekcijom movies_optimized i user_profiles_optimized.")

    start_time = datetime.now()

    user_profile = db.user_profiles_optimized.find_one(
        {"userId": USER_ID},
        {"_id": 0}
    )

    if not user_profile:
        print("Nije pronadjen optimizovani profil korisnika.")
        return

    rated_movie_ids = user_profile.get("ratedMovieIds", [])

    liked_genres = set(user_profile.get("likedGenres", {}).get("ml", []))
    liked_actors = set(user_profile.get("likedActors", {}).get("top", []))
    liked_directors = set(user_profile.get("likedDirectors", []))

    liked_movie_ids = user_profile.get("likedMovieIds", [])

    liked_movies = list(db.movies_optimized.find(
        {"movieId": {"$in": liked_movie_ids}},
        {
            "_id": 0,
            "movieId": 1,
            "title": 1,
            "releaseYear": 1,
            "genres.ml": 1,
            "people.topCastNames": 1,
            "people.directors": 1,
        }
    ))

    query = {
        "movieId": {"$nin": rated_movie_ids},
        "ratingStats.avgRating": {"$gt": MIN_AVG_RATING},
        "ratingStats.ratingCount": {"$gte": MIN_RATING_COUNT},
        "genres.ml": {"$in": list(liked_genres)},
        "$or": [
            {"people.topCastNames": {"$in": list(liked_actors)}},
            {"people.directors": {"$in": list(liked_directors)}},
        ],
    }

    projection = {
        "_id": 0,
        "movieId": 1,
        "tmdbId": 1,
        "title": 1,
        "releaseYear": 1,
        "releaseDecade": 1,
        "genres": 1,
        "people.topCastNames": 1,
        "people.directors": 1,
        "ratingStats": 1,
        "commercial": 1,
        "buckets": 1,
    }

    candidate_movies = list(db.movies_optimized.find(query, projection))

    recommendations = []

    for movie in candidate_movies:
        genres = movie.get("genres", {})
        people = movie.get("people", {})
        rating_stats = movie.get("ratingStats", {})
        commercial = movie.get("commercial", {})
        buckets = movie.get("buckets", {})

        candidate_genres = set(genres.get("ml", []))
        candidate_actors = set(people.get("topCastNames", []))
        candidate_directors = set(people.get("directors", []))

        shared_genres = candidate_genres.intersection(liked_genres)
        shared_actors = candidate_actors.intersection(liked_actors)
        shared_directors = candidate_directors.intersection(liked_directors)

        if len(shared_genres) == 0:
            continue

        if len(shared_actors) == 0 and len(shared_directors) == 0:
            continue

        avg_rating = rating_stats.get("avgRating", 0)
        rating_count = rating_stats.get("ratingCount", 0)

        score = (
            avg_rating * 10
            + min(rating_count / 10000, 5)
            + len(shared_genres) * 2
            + len(shared_actors) * 3
            + len(shared_directors) * 4
        )

        recommendations.append({
            "movieId": movie.get("movieId"),
            "tmdbId": movie.get("tmdbId"),
            "title": movie.get("title"),
            "releaseYear": movie.get("releaseYear"),
            "releaseDecade": movie.get("releaseDecade"),
            "avgRating": avg_rating,
            "ratingCount": rating_count,
            "ratingBucket": buckets.get("ratingBucket"),
            "ratingCountBucket": buckets.get("ratingCountBucket"),
            "genres": sorted(candidate_genres),
            "sharedGenres": sorted(shared_genres),
            "sharedActors": sorted(shared_actors),
            "sharedDirectors": sorted(shared_directors),
            "topActors": sorted(candidate_actors),
            "directors": sorted(candidate_directors),
            "popularity": commercial.get("popularity"),
            "budget": commercial.get("budget"),
            "revenue": commercial.get("revenue"),
            "profitStatus": commercial.get("profitStatus"),
            "score": score,
        })

    recommendations.sort(
        key=lambda item: (
            item["score"],
            item["avgRating"],
            item["ratingCount"]
        ),
        reverse=True
    )

    recommendations = recommendations[:20]

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    lines = []
    lines.append("PITANJE 5 - V2 / REORGANIZOVANA OPTIMIZOVANA SEMA")
    lines.append("=" * 70)
    lines.append(
        "Koje filmove mogu preporuciti korisniku userId = 123, ako trazim filmove koje taj korisnik jos nije ocijenio, "
        "a koji imaju prosjecnu MovieLens ocjenu vecu od 4.0, najmanje 1.000 ocjena, najmanje jedan zajednicki zanr "
        "i najmanje jednog zajednickog glumca iz prva 3 mjesta u cast listi ili istog rezisera sa filmovima koje je "
        "korisnik ranije ocijenio ocjenom 4.5 ili 5.0?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(recommendations)}")
    lines.append("")
    lines.append("Profil korisnika:")
    lines.append(f"- Ukupan broj ocjena korisnika: {user_profile.get('ratingCount')}")
    lines.append(f"- Broj filmova ocijenjenih sa 4.5 ili 5.0: {user_profile.get('likedMovieCount')}")
    lines.append(f"- Zanrovi iz visoko ocijenjenih filmova: {', '.join(sorted(liked_genres))}")
    lines.append(f"- Glumci iz prva 3 mjesta: {', '.join(sorted(liked_actors))}")
    lines.append(f"- Reziseri: {', '.join(sorted(liked_directors))}")
    lines.append("")
    lines.append("Visoko ocijenjeni filmovi korisnika:")

    for movie in liked_movies:
        lines.append(f"- {movie.get('title')} ({movie.get('releaseYear')})")

    lines.append("")
    lines.append("Preporuceni filmovi:")
    lines.append("")

    for index, movie in enumerate(recommendations, start=1):
        lines.append(f"{index}. {movie.get('title')} ({movie.get('releaseYear')})")
        lines.append(f"   MovieLens movieId: {movie.get('movieId')}")
        lines.append(f"   TMDB id: {movie.get('tmdbId')}")
        lines.append(f"   Decenija: {movie.get('releaseDecade')}")
        lines.append(f"   Prosjecna ocjena: {round_number(movie.get('avgRating'))}")
        lines.append(f"   Broj ocjena: {movie.get('ratingCount')}")
        lines.append(f"   Rating bucket: {movie.get('ratingBucket')}")
        lines.append(f"   Rating count bucket: {movie.get('ratingCountBucket')}")
        lines.append(f"   Zajednicki zanrovi: {', '.join(movie.get('sharedGenres') or [])}")
        lines.append(f"   Zajednicki glumci: {', '.join(movie.get('sharedActors') or [])}")
        lines.append(f"   Zajednicki reziseri: {', '.join(movie.get('sharedDirectors') or [])}")
        lines.append(f"   Glumci iz prva 3 mjesta: {', '.join(movie.get('topActors') or [])}")
        lines.append(f"   Reziseri: {', '.join(movie.get('directors') or [])}")
        lines.append(f"   Popularnost: {movie.get('popularity')}")
        lines.append(f"   Budzet: {movie.get('budget')}")
        lines.append(f"   Prihod: {movie.get('revenue')}")
        lines.append(f"   Profit status: {movie.get('profitStatus')}")
        lines.append(f"   Recommendation score: {round_number(movie.get('score'))}")
        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()