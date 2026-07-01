from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v1/results/question_3_v1_results.txt")


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v1 upit za pitanje 3...")
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
                "avgRating": {"$gt": 4.1},
                "ratingCount": {"$gte": 2000}
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
                "metadata.budget": {"$gt": 0},
                "metadata.revenue": {"$gt": 0},
                "metadata.popularity": {"$lt": 15},
                "$expr": {
                    "$gt": ["$metadata.budget", "$metadata.revenue"]
                }
            }
        },
        {
            "$addFields": {
                "lossAmount": {
                    "$subtract": ["$metadata.budget", "$metadata.revenue"]
                },
                "revenueBudgetRatio": {
                    "$divide": ["$metadata.revenue", "$metadata.budget"]
                }
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
                "lossAmount": 1,
                "revenueBudgetRatio": {"$round": ["$revenueBudgetRatio", 3]},
                "popularity": "$metadata.popularity"
            }
        },
        {
            "$sort": {
                "avgRating": -1,
                "ratingCount": -1,
                "lossAmount": -1
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
    lines.append("PITANJE 3 - V1 / NEOPTIMIZOVANA SEMA")
    lines.append("=" * 60)
    lines.append(
        "Koji filmovi imaju prosjecnu MovieLens ocjenu vecu od 4.1, najmanje 2.000 korisnickih ocjena, "
        "TMDB popularnost manju od 15, poznat budzet i prihod, ali budzet veci od prihoda?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(results)}")
    lines.append("")

    for index, movie in enumerate(results, start=1):
        lines.append(f"{index}. {movie.get('title')} ({movie.get('releaseYear')})")
        lines.append(f"   MovieLens movieId: {movie.get('movieId')}")
        lines.append(f"   TMDB id: {movie.get('tmdbId')}")
        lines.append(f"   Zanrovi: {', '.join(movie.get('genres') or [])}")
        lines.append(f"   Prosjecna ocjena: {movie.get('avgRating')}")
        lines.append(f"   Broj ocjena: {movie.get('ratingCount')}")
        lines.append(f"   Budzet: {movie.get('budget')}")
        lines.append(f"   Prihod: {movie.get('revenue')}")
        lines.append(f"   Gubitak prema budzetu: {movie.get('lossAmount')}")
        lines.append(f"   Odnos prihoda i budzeta: {movie.get('revenueBudgetRatio')}")
        lines.append(f"   TMDB popularnost: {movie.get('popularity')}")
        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()