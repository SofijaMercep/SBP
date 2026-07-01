from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v2/results/question_1_v2_results.txt")


def round_number(value, decimals=3):
    if value is None:
        return None

    return round(value, decimals)


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Pokrecem v2 upit za pitanje 1...")
    print("Upit se izvrsava nad novom reorganizovanom kolekcijom movies_optimized.")

    start_time = datetime.now()

    query = {
        "genres.tmdb": "Science Fiction",
        "releaseYear": {"$gt": 2000},
        "ratingStats.avgRating": {"$gt": 4.0},
        "ratingStats.ratingCount": {"$gte": 5000},
        "commercial.budget": {"$gt": 50000000},
        "people.castCount": {"$gte": 3},
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
        "people.topCastNames": 1,
        "people.directors": 1,
        "buckets": 1,
    }

    results = list(
        db.movies_optimized
        .find(query, projection)
        .sort([
            ("ratingStats.avgRating", -1),
            ("ratingStats.ratingCount", -1),
        ])
        .limit(20)
    )

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    lines = []
    lines.append("PITANJE 1 - V2 / REORGANIZOVANA OPTIMIZOVANA SEMA")
    lines.append("=" * 70)
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
        rating_stats = movie.get("ratingStats", {})
        commercial = movie.get("commercial", {})
        genres = movie.get("genres", {})
        people = movie.get("people", {})
        buckets = movie.get("buckets", {})

        lines.append(f"{index}. {movie.get('title')} ({movie.get('releaseYear')})")
        lines.append(f"   MovieLens movieId: {movie.get('movieId')}")
        lines.append(f"   TMDB id: {movie.get('tmdbId')}")
        lines.append(f"   Decenija: {movie.get('releaseDecade')}")
        lines.append(f"   Zanrovi: {', '.join(genres.get('all') or [])}")
        lines.append(f"   Prosjecna ocjena: {round_number(rating_stats.get('avgRating'))}")
        lines.append(f"   Broj ocjena: {rating_stats.get('ratingCount')}")
        lines.append(f"   Rating bucket: {buckets.get('ratingBucket')}")
        lines.append(f"   Rating count bucket: {buckets.get('ratingCountBucket')}")
        lines.append(f"   Budzet: {commercial.get('budget')}")
        lines.append(f"   Prihod: {commercial.get('revenue')}")
        lines.append(f"   Profit status: {commercial.get('profitStatus')}")
        lines.append(f"   Budget bucket: {buckets.get('budgetBucket')}")
        lines.append(f"   Popularnost: {commercial.get('popularity')}")
        lines.append(f"   Glumci iz prva 3 mjesta: {', '.join(people.get('topCastNames') or [])}")
        lines.append(f"   Reziseri: {', '.join(people.get('directors') or [])}")
        lines.append("")

    output = "\n".join(lines)

    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")

    print(f"Rezultat sacuvan u: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()