from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v2/results/question_2_v2_results.txt")


def round_number(value, decimals=3):
    if value is None:
        return None

    return round(value, decimals)


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v2 upit za pitanje 2...")
    print("Upit se izvrsava nad novom reorganizovanom kolekcijom movies_optimized.")

    start_time = datetime.now()

    pipeline = [
        {
            "$match": {
                "ratingStats.avgRating": {"$gt": 4.0},
                "ratingStats.ratingCount": {"$gte": 1000},
                "commercial.profitStatus": "profitable",
            }
        },
        {
            "$unwind": "$people.topCastNames"
        },
        {
            "$group": {
                "_id": "$people.topCastNames",
                "movieCount": {"$sum": 1},
                "avgMovieRating": {"$avg": "$ratingStats.avgRating"},
                "totalRatings": {"$sum": "$ratingStats.ratingCount"},
                "movies": {
                    "$push": {
                        "title": "$title",
                        "releaseYear": "$releaseYear",
                        "avgRating": "$ratingStats.avgRating",
                        "ratingCount": "$ratingStats.ratingCount",
                        "budget": "$commercial.budget",
                        "revenue": "$commercial.revenue",
                        "profit": "$commercial.profit",
                        "profitStatus": "$commercial.profitStatus",
                    }
                }
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
                "avgMovieRating": 1,
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

    results = list(db.movies_optimized.aggregate(pipeline, allowDiskUse=True))

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    lines = []
    lines.append("PITANJE 2 - V2 / REORGANIZOVANA OPTIMIZOVANA SEMA")
    lines.append("=" * 70)
    lines.append(
        "Koji glumci iz prva 3 mjesta u cast listi se najcesce pojavljuju u filmovima "
        "koji imaju prosjecnu MovieLens ocjenu vecu od 4.0, najmanje 1.000 korisnickih ocjena "
        "i prihod veci od budzeta?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(results)}")
    lines.append("")

    for index, actor in enumerate(results, start=1):
        lines.append(f"{index}. {actor.get('actor')}")
        lines.append(f"   Broj filmova: {actor.get('movieCount')}")
        lines.append(f"   Prosjecna ocjena filmova: {round_number(actor.get('avgMovieRating'))}")
        lines.append(f"   Ukupan broj MovieLens ocjena: {actor.get('totalRatings')}")
        lines.append("   Primjeri filmova:")

        for movie in actor.get("movies", []):
            lines.append(
                f"   - {movie.get('title')} ({movie.get('releaseYear')}), "
                f"ocjena: {round_number(movie.get('avgRating'))}, "
                f"broj ocjena: {movie.get('ratingCount')}, "
                f"budzet: {movie.get('budget')}, "
                f"prihod: {movie.get('revenue')}, "
                f"profit: {movie.get('profit')}"
            )

        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()