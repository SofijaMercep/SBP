from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
USER_ID = 123
OUTPUT_FILE = Path("v1/results/question_5_v1_results.txt")

MIN_AVG_RATING = 4.0
MIN_RATING_COUNT = 1000
MIN_USER_LIKED_RATING = 4.5
TOP_CAST_ORDER_LIMIT = 2


def split_genres(genres_value):
    if not genres_value:
        return set()

    return {
        genre.strip()
        for genre in str(genres_value).split("|")
        if genre.strip() and genre.strip() != "(no genres listed)"
    }


def get_top_cast_names(credits_document):
    names = set()

    if not credits_document:
        return names

    for actor in credits_document.get("cast", []):
        actor_order = actor.get("order")
        actor_name = actor.get("name")

        if actor_name is None:
            continue

        if actor_order is not None and actor_order <= TOP_CAST_ORDER_LIMIT:
            names.add(actor_name)

    return names


def get_director_names(credits_document):
    names = set()

    if not credits_document:
        return names

    for director in credits_document.get("directors", []):
        director_name = director.get("name")

        if director_name:
            names.add(director_name)

    return names


def round_number(value, decimals=3):
    if value is None:
        return None

    return round(value, decimals)


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v1 upit za pitanje 5...")
    print("Ovo moze trajati duze jer se radi nad neoptimizovanom semom.")

    start_time = datetime.now()

    # 1. Uzimamo sve ocjene korisnika i izdvajamo filmove koje je ocijenio sa 4.5 ili 5.0.
    user_ratings = list(db.ml_ratings.find(
        {"userId": USER_ID},
        {"_id": 0, "movieId": 1, "rating": 1}
    ))

    rated_movie_ids = {
        rating["movieId"]
        for rating in user_ratings
    }

    liked_movie_ids = [
        rating["movieId"]
        for rating in user_ratings
        if rating.get("rating", 0) >= MIN_USER_LIKED_RATING
    ]

    if len(liked_movie_ids) < 5:
        print("Korisnik nema najmanje 5 filmova ocijenjenih sa 4.5 ili 5.0.")
        return

    # 2. Pravimo profil korisnika: omiljeni zanrovi, glumci iz prva 3 mjesta i reziseri.
    liked_movies = list(db.ml_movies.find(
        {"movieId": {"$in": liked_movie_ids}},
        {"_id": 0, "movieId": 1, "title": 1, "genres": 1}
    ))

    liked_movies_by_id = {
        movie["movieId"]: movie
        for movie in liked_movies
    }

    liked_links = list(db.ml_links.find(
        {"movieId": {"$in": liked_movie_ids}},
        {"_id": 0, "movieId": 1, "tmdbId": 1}
    ))

    liked_movie_to_tmdb = {
        link["movieId"]: link.get("tmdbId")
        for link in liked_links
        if link.get("tmdbId") is not None
    }

    liked_tmdb_ids = list(liked_movie_to_tmdb.values())

    liked_credits = list(db.tmdb_credits.find(
        {"id": {"$in": liked_tmdb_ids}},
        {"_id": 0, "id": 1, "cast": 1, "directors": 1}
    ))

    liked_credits_by_tmdb = {
        credits["id"]: credits
        for credits in liked_credits
    }

    liked_genres = set()
    liked_actors = set()
    liked_directors = set()

    liked_movie_details = []

    for movie_id in liked_movie_ids:
        movie = liked_movies_by_id.get(movie_id)
        tmdb_id = liked_movie_to_tmdb.get(movie_id)
        credits = liked_credits_by_tmdb.get(tmdb_id)

        if not movie:
            continue

        movie_genres = split_genres(movie.get("genres"))
        movie_actors = get_top_cast_names(credits)
        movie_directors = get_director_names(credits)

        liked_genres.update(movie_genres)
        liked_actors.update(movie_actors)
        liked_directors.update(movie_directors)

        liked_movie_details.append({
            "movieId": movie_id,
            "title": movie.get("title"),
            "genres": sorted(movie_genres),
            "topActors": sorted(movie_actors),
            "directors": sorted(movie_directors),
        })

    # 3. Racunamo prosjecnu ocjenu i broj ocjena za sve filmove.
    ratings_pipeline = [
        {
            "$group": {
                "_id": "$movieId",
                "avgRating": {"$avg": "$rating"},
                "ratingCount": {"$sum": 1}
            }
        },
        {
            "$match": {
                "avgRating": {"$gt": MIN_AVG_RATING},
                "ratingCount": {"$gte": MIN_RATING_COUNT}
            }
        }
    ]

    rating_results = list(db.ml_ratings.aggregate(
        ratings_pipeline,
        allowDiskUse=True
    ))

    rating_stats = {
        result["_id"]: {
            "avgRating": result["avgRating"],
            "ratingCount": result["ratingCount"]
        }
        for result in rating_results
        if result["_id"] not in rated_movie_ids
    }

    candidate_movie_ids = list(rating_stats.keys())

    # 4. Uzimamo osnovne podatke o kandidatima.
    candidate_movies = list(db.ml_movies.find(
        {"movieId": {"$in": candidate_movie_ids}},
        {"_id": 0, "movieId": 1, "title": 1, "genres": 1}
    ))

    candidate_movies_by_id = {
        movie["movieId"]: movie
        for movie in candidate_movies
    }

    candidate_links = list(db.ml_links.find(
        {"movieId": {"$in": candidate_movie_ids}},
        {"_id": 0, "movieId": 1, "tmdbId": 1}
    ))

    candidate_movie_to_tmdb = {
        link["movieId"]: link.get("tmdbId")
        for link in candidate_links
        if link.get("tmdbId") is not None
    }

    candidate_tmdb_ids = list(set(candidate_movie_to_tmdb.values()))

    candidate_metadata = list(db.tmdb_movies_metadata.find(
        {"id": {"$in": candidate_tmdb_ids}},
        {
            "_id": 0,
            "id": 1,
            "title": 1,
            "release_year": 1,
            "popularity": 1,
            "budget": 1,
            "revenue": 1
        }
    ))

    candidate_credits = list(db.tmdb_credits.find(
        {"id": {"$in": candidate_tmdb_ids}},
        {"_id": 0, "id": 1, "cast": 1, "directors": 1}
    ))

    metadata_by_tmdb = {
        metadata["id"]: metadata
        for metadata in candidate_metadata
    }

    credits_by_tmdb = {
        credits["id"]: credits
        for credits in candidate_credits
    }

    # 5. Filtriramo kandidate prema slicnosti sa profilom korisnika.
    recommendations = []

    for movie_id in candidate_movie_ids:
        movie = candidate_movies_by_id.get(movie_id)
        tmdb_id = candidate_movie_to_tmdb.get(movie_id)

        if not movie or tmdb_id is None:
            continue

        metadata = metadata_by_tmdb.get(tmdb_id)
        credits = credits_by_tmdb.get(tmdb_id)

        if not metadata or not credits:
            continue

        candidate_genres = split_genres(movie.get("genres"))
        candidate_actors = get_top_cast_names(credits)
        candidate_directors = get_director_names(credits)

        shared_genres = candidate_genres.intersection(liked_genres)
        shared_actors = candidate_actors.intersection(liked_actors)
        shared_directors = candidate_directors.intersection(liked_directors)

        if len(shared_genres) == 0:
            continue

        if len(shared_actors) == 0 and len(shared_directors) == 0:
            continue

        stats = rating_stats[movie_id]

        score = (
            stats["avgRating"] * 10
            + min(stats["ratingCount"] / 10000, 5)
            + len(shared_genres) * 2
            + len(shared_actors) * 3
            + len(shared_directors) * 4
        )

        recommendations.append({
            "movieId": movie_id,
            "tmdbId": tmdb_id,
            "title": metadata.get("title") or movie.get("title"),
            "releaseYear": metadata.get("release_year"),
            "avgRating": stats["avgRating"],
            "ratingCount": stats["ratingCount"],
            "genres": sorted(candidate_genres),
            "sharedGenres": sorted(shared_genres),
            "sharedActors": sorted(shared_actors),
            "sharedDirectors": sorted(shared_directors),
            "topActors": sorted(candidate_actors),
            "directors": sorted(candidate_directors),
            "popularity": metadata.get("popularity"),
            "budget": metadata.get("budget"),
            "revenue": metadata.get("revenue"),
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

    # 6. Ispis i cuvanje rezultata.
    lines = []
    lines.append("PITANJE 5 - V1 / NEOPTIMIZOVANA SEMA")
    lines.append("=" * 60)
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
    lines.append(f"- Ukupan broj ocjena korisnika: {len(user_ratings)}")
    lines.append(f"- Broj filmova ocijenjenih sa 4.5 ili 5.0: {len(liked_movie_ids)}")
    lines.append(f"- Zanrovi iz visoko ocijenjenih filmova: {', '.join(sorted(liked_genres))}")
    lines.append(f"- Glumci iz prva 3 mjesta: {', '.join(sorted(liked_actors))}")
    lines.append(f"- Reziseri: {', '.join(sorted(liked_directors))}")
    lines.append("")
    lines.append("Visoko ocijenjeni filmovi korisnika:")
    for movie in liked_movie_details:
        lines.append(f"- {movie.get('title')}")
    lines.append("")
    lines.append("Preporuceni filmovi:")
    lines.append("")

    for index, movie in enumerate(recommendations, start=1):
        lines.append(f"{index}. {movie.get('title')} ({movie.get('releaseYear')})")
        lines.append(f"   MovieLens movieId: {movie.get('movieId')}")
        lines.append(f"   TMDB id: {movie.get('tmdbId')}")
        lines.append(f"   Prosjecna ocjena: {round_number(movie.get('avgRating'))}")
        lines.append(f"   Broj ocjena: {movie.get('ratingCount')}")
        lines.append(f"   Zajednicki zanrovi: {', '.join(movie.get('sharedGenres') or [])}")
        lines.append(f"   Zajednicki glumci: {', '.join(movie.get('sharedActors') or [])}")
        lines.append(f"   Zajednicki reziseri: {', '.join(movie.get('sharedDirectors') or [])}")
        lines.append(f"   Glumci iz prva 3 mjesta: {', '.join(movie.get('topActors') or [])}")
        lines.append(f"   Reziseri: {', '.join(movie.get('directors') or [])}")
        lines.append(f"   Popularnost: {movie.get('popularity')}")
        lines.append(f"   Budzet: {movie.get('budget')}")
        lines.append(f"   Prihod: {movie.get('revenue')}")
        lines.append(f"   Recommendation score: {round_number(movie.get('score'))}")
        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()