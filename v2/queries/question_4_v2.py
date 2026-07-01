from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v2/results/question_4_v2_results.txt")

TARGET_TAGS = [
    "dark",
    "psychological",
    "plot twist",
    "twist",
    "twist ending",
    "twists & turns",
]


def round_number(value, decimals=3):
    if value is None:
        return None

    return round(value, decimals)


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v2 upit za pitanje 4...")
    print("Upit se izvrsava nad novom reorganizovanom kolekcijom movies_optimized.")

    start_time = datetime.now()

    query = {
        "ratingStats.avgRating": {"$gt": 4.0},
        "ratingStats.ratingCount": {"$gte": 1000},
        "genome.highRelevanceTagNames": {"$in": TARGET_TAGS},
        "people.directors": {"$ne": []},
    }

    projection = {
        "_id": 0,
        "movieId": 1,
        "tmdbId": 1,
        "title": 1,
        "releaseYear": 1,
        "ratingStats": 1,
        "people.directors": 1,
        "genome.highRelevanceTags": 1,
        "buckets": 1,
    }

    movies = list(db.movies_optimized.find(query, projection))

    directors = {}

    for movie in movies:
        rating_stats = movie.get("ratingStats", {})
        people = movie.get("people", {})
        genome = movie.get("genome", {})

        matched_tags = [
            tag for tag in genome.get("highRelevanceTags", [])
            if tag.get("tag") in TARGET_TAGS
        ]

        if not matched_tags:
            continue

        movie_info = {
            "movieId": movie.get("movieId"),
            "tmdbId": movie.get("tmdbId"),
            "title": movie.get("title"),
            "releaseYear": movie.get("releaseYear"),
            "avgRating": rating_stats.get("avgRating"),
            "ratingCount": rating_stats.get("ratingCount"),
            "ratingBucket": movie.get("buckets", {}).get("ratingBucket"),
            "matchedTags": matched_tags,
        }

        for director_name in people.get("directors", []):
            if not director_name:
                continue

            if director_name not in directors:
                directors[director_name] = {
                    "director": director_name,
                    "movies": {}
                }

            directors[director_name]["movies"][movie.get("movieId")] = movie_info

    results = []

    for director_data in directors.values():
        director_movies = list(director_data["movies"].values())

        if len(director_movies) < 3:
            continue

        avg_director_rating = sum(
            movie["avgRating"] for movie in director_movies
        ) / len(director_movies)

        total_ratings = sum(
            movie["ratingCount"] for movie in director_movies
        )

        all_matched_tags = sorted({
            tag.get("tag")
            for movie in director_movies
            for tag in movie.get("matchedTags", [])
            if tag.get("tag")
        })

        results.append({
            "director": director_data["director"],
            "movieCount": len(director_movies),
            "avgDirectorRating": avg_director_rating,
            "totalRatings": total_ratings,
            "matchedTags": all_matched_tags,
            "movies": director_movies,
        })

    results.sort(
        key=lambda item: (
            item["movieCount"],
            item["avgDirectorRating"],
            item["totalRatings"]
        ),
        reverse=True
    )

    results = results[:20]

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    lines = []
    lines.append("PITANJE 4 - V2 / REORGANIZOVANA OPTIMIZOVANA SEMA")
    lines.append("=" * 70)
    lines.append(
        "Koji reziseri imaju najmanje 3 filma sa prosjecnom MovieLens ocjenom vecom od 4.0, "
        "najmanje 1.000 korisnickih ocjena po filmu i genome tagom 'dark', 'psychological', "
        "'plot twist', 'twist', 'twist ending' ili 'twists & turns', pri cemu je relevantnost taga veca od 0.7?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(results)}")
    lines.append("")

    for index, director in enumerate(results, start=1):
        lines.append(f"{index}. {director.get('director')}")
        lines.append(f"   Broj filmova: {director.get('movieCount')}")
        lines.append(f"   Prosjecna ocjena filmova: {round_number(director.get('avgDirectorRating'))}")
        lines.append(f"   Ukupan broj MovieLens ocjena: {director.get('totalRatings')}")
        lines.append(f"   Zajednicki relevantni tagovi: {', '.join(director.get('matchedTags') or [])}")
        lines.append("   Primjeri filmova i tagova:")

        for movie in director.get("movies", [])[:8]:
            tags_text = ", ".join([
                f"{tag.get('tag')} ({round_number(tag.get('relevance'))})"
                for tag in movie.get("matchedTags", [])
            ])

            lines.append(
                f"   - {movie.get('title')} ({movie.get('releaseYear')}), "
                f"ocjena: {round_number(movie.get('avgRating'))}, "
                f"broj ocjena: {movie.get('ratingCount')}, "
                f"rating bucket: {movie.get('ratingBucket')}, "
                f"tagovi: {tags_text}"
            )

        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()