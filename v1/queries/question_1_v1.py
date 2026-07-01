from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v1/results/question_1_v1_results.txt")


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v1 upit za pitanje 1...")
    print("Ovo moze trajati duze jer se radi nad neoptimizovanom semom.")

    start_time = datetime.now()

    pipeline = [
        {
            "$group": {
                "_id": "$movieId",
                "avgRating": {"$avg": "$rating"},
                "ratingCount": {"$sum": 1}
            }
        },
        {
            "$match": {
                "avgRating": {"$gt": 4.0},
                "ratingCount": {"$gte": 5000}
            }
        },
        {
            "$lookup": {
                "from": "ml_links",
                "localField": "_id",
                "foreignField": "movieId",
                "as": "link"
            }
        },
        {
            "$unwind": "$link"
        },
        {
            "$lookup": {
                "from": "tmdb_movies_metadata",
                "localField": "link.tmdbId",
                "foreignField": "id",
                "as": "metadata"
            }
        },
        {
            "$unwind": "$metadata"
        },
        {
            "$match": {
                "metadata.release_year": {"$gt": 2000},
                "metadata.genres": "Science Fiction",
                "metadata.budget": {"$gt": 50000000}
            }
        },
        {
            "$lookup": {
                "from": "tmdb_credits",
                "localField": "link.tmdbId",
                "foreignField": "id",
                "as": "credits"
            }
        },
        {
            "$unwind": "$credits"
        },
        {
            "$addFields": {
                "castCount": {"$size": "$credits.cast"}
            }
        },
        {
            "$match": {
                "castCount": {"$gte": 3}
            }
        },
        {
            "$project": {
                "_id": 0,
                "movieId": "$_id",
                "tmdbId": "$link.tmdbId",
                "title": "$metadata.title",
                "releaseYear": "$metadata.release_year",
                "genres": "$metadata.genres",
                "avgRating": {"$round": ["$avgRating", 3]},
                "ratingCount": 1,
                "budget": "$metadata.budget",
                "revenue": "$metadata.revenue",
                "popularity": "$metadata.popularity",
                "firstThreeCast": {"$slice": ["$credits.cast.name", 3]},
                "directors": "$credits.directors.name"
            }
        },
        {
            "$sort": {
                "avgRating": -1,
                "ratingCount": -1
            }
        },
        {
            "$limit": 20
        }
    ]

    results = list(db.ml_ratings.aggregate(pipeline, allowDiskUse=True))

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    lines = []
    lines.append("PITANJE 1 - V1 / NEOPTIMIZOVANA SEMA")
    lines.append("=" * 60)
    lines.append(
        "Koje Science Fiction filmove objavljene poslije 2000. godine mogu preporuciti siroj publici "
        "ako imaju prosjecnu MovieLens ocjenu vecu od 4.0, najmanje 5.000 korisnickih ocjena, "
        "budzet veci od 50 miliona dolara i najmanje 3 glumca u cast listi?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(results)}")
    lines.append("")

    for index, movie in enumerate(results, start=1):
        lines.append(f"{index}. {movie.get('title')} ({movie.get('releaseYear')})")
        lines.append(f"   MovieLens movieId: {movie.get('movieId')}")
        lines.append(f"   TMDB id: {movie.get('tmdbId')}")
        lines.append(f"   Prosjecna ocjena: {movie.get('avgRating')}")
        lines.append(f"   Broj ocjena: {movie.get('ratingCount')}")
        lines.append(f"   Budzet: {movie.get('budget')}")
        lines.append(f"   Prihod: {movie.get('revenue')}")
        lines.append(f"   Popularnost: {movie.get('popularity')}")
        lines.append(f"   Glumci: {', '.join(movie.get('firstThreeCast') or [])}")
        lines.append(f"   Reziseri: {', '.join(movie.get('directors') or [])}")
        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()