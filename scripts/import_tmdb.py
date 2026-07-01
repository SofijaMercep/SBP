import ast
import csv
import sys
from datetime import datetime

from pymongo import MongoClient


# Windows nekad ne prihvata sys.maxsize direktno, zato ga smanjujemo dok ne bude validan.
max_csv_field_size = sys.maxsize

while True:
    try:
        csv.field_size_limit(max_csv_field_size)
        break
    except OverflowError:
        max_csv_field_size = int(max_csv_field_size / 10)


DB_NAME = "movie_recommendation_db"

MOVIES_METADATA_FILE = "data/tmdb/movies_metadata.csv"
CREDITS_FILE = "data/tmdb/credits.csv"
KEYWORDS_FILE = "data/tmdb/keywords.csv"

BATCH_SIZE = 1000


def parse_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (ValueError, TypeError):
        return None


def parse_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_year(value):
    try:
        if value is None or value == "":
            return None
        return datetime.strptime(value, "%Y-%m-%d").year
    except (ValueError, TypeError):
        return None


def parse_literal_list(value):
    if value is None or value == "":
        return []

    try:
        parsed = ast.literal_eval(value)

        if isinstance(parsed, list):
            return parsed

        return []
    except (ValueError, SyntaxError):
        return []


def extract_names(items):
    names = []

    for item in items:
        if isinstance(item, dict) and item.get("name"):
            names.append(item["name"])

    return names


def extract_cast(cast_items):
    cast = []

    for item in cast_items:
        if not isinstance(item, dict):
            continue

        name = item.get("name")

        if not name:
            continue

        cast.append({
            "id": parse_int(item.get("id")),
            "name": name,
            "character": item.get("character"),
            "order": parse_int(item.get("order")),
        })

    return cast


def extract_directors(crew_items):
    directors = []

    for item in crew_items:
        if not isinstance(item, dict):
            continue

        if item.get("job") == "Director" and item.get("name"):
            directors.append({
                "id": parse_int(item.get("id")),
                "name": item.get("name"),
            })

    return directors


def insert_batch(collection, batch):
    if len(batch) > 0:
        collection.insert_many(batch)


def import_movies_metadata(db):
    collection = db.tmdb_movies_metadata
    collection.drop()

    batch = []
    imported = 0
    skipped = 0

    with open(MOVIES_METADATA_FILE, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movie_id = parse_int(row.get("id"))

            if movie_id is None:
                skipped += 1
                continue

            genres_raw = parse_literal_list(row.get("genres"))
            production_companies_raw = parse_literal_list(row.get("production_companies"))
            production_countries_raw = parse_literal_list(row.get("production_countries"))
            spoken_languages_raw = parse_literal_list(row.get("spoken_languages"))

            document = {
                "id": movie_id,
                "imdb_id": row.get("imdb_id") or None,
                "title": row.get("title") or None,
                "original_title": row.get("original_title") or None,
                "overview": row.get("overview") or None,
                "original_language": row.get("original_language") or None,
                "release_date": row.get("release_date") or None,
                "release_year": parse_year(row.get("release_date")),
                "budget": parse_int(row.get("budget")),
                "revenue": parse_int(row.get("revenue")),
                "popularity": parse_float(row.get("popularity")),
                "vote_average": parse_float(row.get("vote_average")),
                "vote_count": parse_int(row.get("vote_count")),
                "runtime": parse_float(row.get("runtime")),
                "status": row.get("status") or None,
                "genres": extract_names(genres_raw),
                "production_companies": extract_names(production_companies_raw),
                "production_countries": extract_names(production_countries_raw),
                "spoken_languages": extract_names(spoken_languages_raw),
            }

            batch.append(document)
            imported += 1

            if len(batch) >= BATCH_SIZE:
                insert_batch(collection, batch)
                batch = []

    insert_batch(collection, batch)

    print(f"tmdb_movies_metadata imported: {imported}")
    print(f"tmdb_movies_metadata skipped: {skipped}")


def import_credits(db):
    collection = db.tmdb_credits
    collection.drop()

    batch = []
    imported = 0
    skipped = 0

    with open(CREDITS_FILE, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movie_id = parse_int(row.get("id"))

            if movie_id is None:
                skipped += 1
                continue

            cast_raw = parse_literal_list(row.get("cast"))
            crew_raw = parse_literal_list(row.get("crew"))

            document = {
                "id": movie_id,
                "cast": extract_cast(cast_raw),
                "directors": extract_directors(crew_raw),
            }

            batch.append(document)
            imported += 1

            if len(batch) >= BATCH_SIZE:
                insert_batch(collection, batch)
                batch = []

    insert_batch(collection, batch)

    print(f"tmdb_credits imported: {imported}")
    print(f"tmdb_credits skipped: {skipped}")


def import_keywords(db):
    collection = db.tmdb_keywords
    collection.drop()

    batch = []
    imported = 0
    skipped = 0

    with open(KEYWORDS_FILE, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            movie_id = parse_int(row.get("id"))

            if movie_id is None:
                skipped += 1
                continue

            keywords_raw = parse_literal_list(row.get("keywords"))

            document = {
                "id": movie_id,
                "keywords": extract_names(keywords_raw),
            }

            batch.append(document)
            imported += 1

            if len(batch) >= BATCH_SIZE:
                insert_batch(collection, batch)
                batch = []

    insert_batch(collection, batch)

    print(f"tmdb_keywords imported: {imported}")
    print(f"tmdb_keywords skipped: {skipped}")


def main():
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    print("Import TMDB podataka pocinje...")

    import_movies_metadata(db)
    import_credits(db)
    import_keywords(db)

    print("TMDB import zavrsen.")


if __name__ == "__main__":
    main()