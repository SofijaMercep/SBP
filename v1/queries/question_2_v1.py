from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v1/results/question_2_v1_results.txt")


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v1 upit za pitanje 2...")
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
                "ratingCount": {"$gte": 1000}
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
                "$expr": {
                    "$gt": ["$metadata.revenue", "$metadata.budget"]
                }
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
            "$unwind": "$credits.cast"
        },
        {
            "$match": {
                "credits.cast.name": {"$ne": None},
                "credits.cast.order": {"$lte": 2}
            }
        },
        {
            "$group": {
                "_id": "$credits.cast.name",
                "movieCount": {"$sum": 1},
                "movies": {
                    "$push": {
                        "title": "$metadata.title",
                        "releaseYear": "$metadata.release_year",
                        "avgRating": {"$round": ["$avgRating", 3]},
                        "ratingCount": "$ratingCount",
                        "budget": "$metadata.budget",
                        "revenue": "$metadata.revenue"
                    }
                },
                "avgMovieRating": {"$avg": "$avgRating"},
                "totalRatings": {"$sum": "$ratingCount"}
            }
        },
        {
            "$match": {
                "movieCount": {"$gte": 2}
            }
        },
        {
            "$project": {
                "_id": 0,
                "actor": "$_id",
                "movieCount": 1,
                "avgMovieRating": {"$round": ["$avgMovieRating", 3]},
                "totalRatings": 1,
                "movies": {"$slice": ["$movies", 5]}
            }
        },
        {
            "$sort": {
                "movieCount": -1,
                "avgMovieRating": -1,
                "totalRatings": -1
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
    lines.append("PITANJE 2 - V1 / NEOPTIMIZOVANA SEMA")
    lines.append("=" * 60)
    lines.append(
        "Koji glumci iz prvih 3 mjesta u cast listi se najcesce pojavljuju u filmovima koji imaju prosjecnu MovieLens ocjenu "
        "vecu od 4.0, najmanje 1.000 korisnickih ocjena i prihod veci od budzeta?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(results)}")
    lines.append("")

    for index, actor in enumerate(results, start=1):
        lines.append(f"{index}. {actor.get('actor')}")
        lines.append(f"   Broj filmova: {actor.get('movieCount')}")
        lines.append(f"   Prosjecna ocjena filmova: {actor.get('avgMovieRating')}")
        lines.append(f"   Ukupan broj MovieLens ocjena: {actor.get('totalRatings')}")
        lines.append("   Primjeri filmova:")

        for movie in actor.get("movies", []):
            lines.append(
                f"   - {movie.get('title')} ({movie.get('releaseYear')}), "
                f"ocjena: {movie.get('avgRating')}, "
                f"broj ocjena: {movie.get('ratingCount')}, "
                f"budzet: {movie.get('budget')}, "
                f"prihod: {movie.get('revenue')}"
            )

        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()