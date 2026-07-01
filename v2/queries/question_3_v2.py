from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v2/results/question_3_v2_results.txt")


def round_number(value, decimals=3):
    if value is None:
        return None

    return round(value, decimals)


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v2 upit za pitanje 3...")
    print("Upit se izvrsava nad novom reorganizovanom kolekcijom movies_optimized.")

    start_time = datetime.now()

    query = {
        "ratingStats.avgRating": {"$gt": 4.1},
        "ratingStats.ratingCount": {"$gte": 2000},
        "commercial.popularity": {"$lt": 15},
        "commercial.budget": {"$gt": 0},
        "commercial.revenue": {"$gt": 0},
        "commercial.profitStatus": "not_profitable",
    }

    projection = {
        "_id": 0,
        "movieId": 1,
        "tmdbId": 1,
        "title": 1,
        "releaseYear": 1,
        "releaseDecade": 1,
        "genres": 1,
        "ratingStats": 1,
        "commercial": 1,
        "buckets": 1,
    }

    results = list(
        db.movies_optimized
        .find(query, projection)
        .sort([
            ("ratingStats.avgRating", -1),
            ("ratingStats.ratingCount", -1),
            ("commercial.profit", 1),
        ])
        .limit(20)
    )

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    lines = []
    lines.append("PITANJE 3 - V2 / REORGANIZOVANA OPTIMIZOVANA SEMA")
    lines.append("=" * 70)
    lines.append(
        "Koji filmovi imaju prosjecnu MovieLens ocjenu vecu od 4.1, najmanje 2.000 korisnickih ocjena, "
        "TMDB popularnost manju od 15, poznat budzet i prihod, ali budzet veci od prihoda?"
    )
    lines.append("")
    lines.append(f"Vrijeme izvrsavanja: {duration_seconds:.3f} sekundi")
    lines.append(f"Broj rezultata: {len(results)}")
    lines.append("")

    for index, movie in enumerate(results, start=1):
        rating_stats = movie.get("ratingStats", {})
        commercial = movie.get("commercial", {})
        buckets = movie.get("buckets", {})
        genres = movie.get("genres", {})

        lines.append(f"{index}. {movie.get('title')} ({movie.get('releaseYear')})")
        lines.append(f"   MovieLens movieId: {movie.get('movieId')}")
        lines.append(f"   TMDB id: {movie.get('tmdbId')}")
        lines.append(f"   Decenija: {movie.get('releaseDecade')}")
        lines.append(f"   Zanrovi: {', '.join(genres.get('all') or [])}")
        lines.append(f"   Prosjecna ocjena: {round_number(rating_stats.get('avgRating'))}")
        lines.append(f"   Broj ocjena: {rating_stats.get('ratingCount')}")
        lines.append(f"   Rating bucket: {buckets.get('ratingBucket')}")
        lines.append(f"   Budzet: {commercial.get('budget')}")
        lines.append(f"   Prihod: {commercial.get('revenue')}")
        lines.append(f"   Profit: {commercial.get('profit')}")
        lines.append(f"   Profit status: {commercial.get('profitStatus')}")
        lines.append(f"   Profit bucket: {buckets.get('profitBucket')}")
        lines.append(f"   Odnos prihoda i budzeta: {round_number(commercial.get('revenueBudgetRatio'))}")
        lines.append(f"   TMDB popularnost: {commercial.get('popularity')}")
        lines.append(f"   Popularity bucket: {buckets.get('popularityBucket')}")
        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()