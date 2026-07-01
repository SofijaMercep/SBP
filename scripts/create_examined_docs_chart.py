from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

OUTPUT_CSV = RESULTS_DIR / "examined_docs_comparison.csv"
OUTPUT_TXT = RESULTS_DIR / "examined_docs_comparison.txt"
OUTPUT_CHART = CHARTS_DIR / "pregledani_dokumenti_po_upitu.png"

USER_ID = 123

MIN_AVG_RATING = 4.0
MIN_RATING_COUNT = 1000
MIN_USER_LIKED_RATING = 4.5
TOP_CAST_ORDER_LIMIT = 2

TARGET_TAGS = [
    "dark",
    "psychological",
    "plot twist",
    "twist",
    "twist ending",
    "twists & turns",
]


def explain_aggregate(db, collection_name: str, pipeline: list[dict[str, Any]]) -> dict[str, Any]:
    return db.command(
        "explain",
        {
            "aggregate": collection_name,
            "pipeline": pipeline,
            "cursor": {},
            "allowDiskUse": True,
        },
        verbosity="executionStats",
    )


def explain_find(
    db,
    collection_name: str,
    query: dict[str, Any],
    projection: dict[str, Any] | None = None,
    sort: list[tuple[str, int]] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    command: dict[str, Any] = {
        "find": collection_name,
        "filter": query,
    }

    if projection is not None:
        command["projection"] = projection

    if sort is not None:
        command["sort"] = dict(sort)

    if limit is not None:
        command["limit"] = limit

    return db.command("explain", command, verbosity="executionStats")


def sum_key(data: Any, key: str) -> int:
    total = 0

    if isinstance(data, dict):
        for current_key, value in data.items():
            if current_key == key and isinstance(value, (int, float)):
                total += int(value)
            else:
                total += sum_key(value, key)

    elif isinstance(data, list):
        for item in data:
            total += sum_key(item, key)

    return total


def collect_stats(explain: dict[str, Any]) -> dict[str, int]:
    return {
        "docsExamined": sum_key(explain, "totalDocsExamined"),
        "keysExamined": sum_key(explain, "totalKeysExamined"),
        "nReturned": sum_key(explain, "nReturned"),
    }


def add_stats(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {
        "docsExamined": left.get("docsExamined", 0) + right.get("docsExamined", 0),
        "keysExamined": left.get("keysExamined", 0) + right.get("keysExamined", 0),
        "nReturned": left.get("nReturned", 0) + right.get("nReturned", 0),
    }


def empty_stats() -> dict[str, int]:
    return {
        "docsExamined": 0,
        "keysExamined": 0,
        "nReturned": 0,
    }


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


def v1_question_1(db):
    pipeline = [
        {"$group": {"_id": "$movieId", "avgRating": {"$avg": "$rating"}, "ratingCount": {"$sum": 1}}},
        {"$match": {"avgRating": {"$gt": 4.0}, "ratingCount": {"$gte": 5000}}},
        {"$lookup": {"from": "ml_links", "localField": "_id", "foreignField": "movieId", "as": "link"}},
        {"$unwind": "$link"},
        {"$lookup": {"from": "tmdb_movies_metadata", "localField": "link.tmdbId", "foreignField": "id", "as": "metadata"}},
        {"$unwind": "$metadata"},
        {"$match": {"metadata.release_year": {"$gt": 2000}, "metadata.genres": "Science Fiction", "metadata.budget": {"$gt": 50000000}}},
        {"$lookup": {"from": "tmdb_credits", "localField": "link.tmdbId", "foreignField": "id", "as": "credits"}},
        {"$unwind": "$credits"},
        {"$addFields": {"castCount": {"$size": "$credits.cast"}}},
        {"$match": {"castCount": {"$gte": 3}}},
        {"$project": {"_id": 0, "movieId": "$_id", "tmdbId": "$link.tmdbId", "title": "$metadata.title", "releaseYear": "$metadata.release_year", "avgRating": {"$round": ["$avgRating", 3]}, "ratingCount": 1}},
        {"$sort": {"avgRating": -1, "ratingCount": -1}},
        {"$limit": 20},
    ]

    return collect_stats(explain_aggregate(db, "ml_ratings", pipeline))


def v2_question_1(db):
    query = {
        "genres.tmdb": "Science Fiction",
        "releaseYear": {"$gt": 2000},
        "ratingStats.avgRating": {"$gt": 4.0},
        "ratingStats.ratingCount": {"$gte": 5000},
        "commercial.budget": {"$gt": 50000000},
        "people.castCount": {"$gte": 3},
    }

    return collect_stats(explain_find(
        db,
        "movies_optimized",
        query,
        projection={"_id": 0, "movieId": 1, "title": 1, "ratingStats": 1},
        sort=[("ratingStats.avgRating", -1), ("ratingStats.ratingCount", -1)],
        limit=20,
    ))


def v1_question_2(db):
    pipeline = [
        {"$group": {"_id": "$movieId", "avgRating": {"$avg": "$rating"}, "ratingCount": {"$sum": 1}}},
        {"$match": {"avgRating": {"$gt": 4.0}, "ratingCount": {"$gte": 1000}}},
        {"$lookup": {"from": "ml_links", "localField": "_id", "foreignField": "movieId", "as": "link"}},
        {"$unwind": "$link"},
        {"$lookup": {"from": "tmdb_movies_metadata", "localField": "link.tmdbId", "foreignField": "id", "as": "metadata"}},
        {"$unwind": "$metadata"},
        {"$match": {"metadata.budget": {"$gt": 0}, "metadata.revenue": {"$gt": 0}, "$expr": {"$gt": ["$metadata.revenue", "$metadata.budget"]}}},
        {"$lookup": {"from": "tmdb_credits", "localField": "link.tmdbId", "foreignField": "id", "as": "credits"}},
        {"$unwind": "$credits"},
        {"$unwind": "$credits.cast"},
        {"$match": {"credits.cast.name": {"$ne": None}, "credits.cast.order": {"$lte": 2}}},
        {"$group": {"_id": "$credits.cast.name", "movieCount": {"$sum": 1}, "avgMovieRating": {"$avg": "$avgRating"}, "totalRatings": {"$sum": "$ratingCount"}}},
        {"$match": {"movieCount": {"$gte": 2}}},
        {"$sort": {"movieCount": -1, "avgMovieRating": -1, "totalRatings": -1}},
        {"$limit": 20},
    ]

    return collect_stats(explain_aggregate(db, "ml_ratings", pipeline))


def v2_question_2(db):
    pipeline = [
        {"$match": {"ratingStats.avgRating": {"$gt": 4.0}, "ratingStats.ratingCount": {"$gte": 1000}, "commercial.profitStatus": "profitable"}},
        {"$unwind": "$people.topCastNames"},
        {"$group": {"_id": "$people.topCastNames", "movieCount": {"$sum": 1}, "avgMovieRating": {"$avg": "$ratingStats.avgRating"}, "totalRatings": {"$sum": "$ratingStats.ratingCount"}}},
        {"$match": {"movieCount": {"$gte": 2}}},
        {"$sort": {"movieCount": -1, "avgMovieRating": -1, "totalRatings": -1}},
        {"$limit": 20},
    ]

    return collect_stats(explain_aggregate(db, "movies_optimized", pipeline))


def v1_question_3(db):
    pipeline = [
        {"$group": {"_id": "$movieId", "avgRating": {"$avg": "$rating"}, "ratingCount": {"$sum": 1}}},
        {"$match": {"avgRating": {"$gt": 4.1}, "ratingCount": {"$gte": 2000}}},
        {"$lookup": {"from": "ml_links", "localField": "_id", "foreignField": "movieId", "as": "link"}},
        {"$unwind": "$link"},
        {"$lookup": {"from": "tmdb_movies_metadata", "localField": "link.tmdbId", "foreignField": "id", "as": "metadata"}},
        {"$unwind": "$metadata"},
        {"$match": {"metadata.budget": {"$gt": 0}, "metadata.revenue": {"$gt": 0}, "metadata.popularity": {"$lt": 15}, "$expr": {"$gt": ["$metadata.budget", "$metadata.revenue"]}}},
        {"$addFields": {"lossAmount": {"$subtract": ["$metadata.budget", "$metadata.revenue"]}}},
        {"$sort": {"avgRating": -1, "ratingCount": -1, "lossAmount": -1}},
        {"$limit": 20},
    ]

    return collect_stats(explain_aggregate(db, "ml_ratings", pipeline))


def v2_question_3(db):
    query = {
        "ratingStats.avgRating": {"$gt": 4.1},
        "ratingStats.ratingCount": {"$gte": 2000},
        "commercial.popularity": {"$lt": 15},
        "commercial.budget": {"$gt": 0},
        "commercial.revenue": {"$gt": 0},
        "commercial.profitStatus": "not_profitable",
    }

    return collect_stats(explain_find(
        db,
        "movies_optimized",
        query,
        projection={"_id": 0, "movieId": 1, "title": 1, "ratingStats": 1, "commercial": 1},
        sort=[("ratingStats.avgRating", -1), ("ratingStats.ratingCount", -1), ("commercial.profit", 1)],
        limit=20,
    ))


def v1_question_4(db):
    total = empty_stats()

    tag_query = {"tag": {"$in": TARGET_TAGS}}
    tag_projection = {"_id": 0, "tagId": 1, "tag": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_genome_tags", tag_query, tag_projection)))
    tag_documents = list(db.ml_genome_tags.find(tag_query, tag_projection))

    tag_id_to_name = {tag_document["tagId"]: tag_document["tag"] for tag_document in tag_documents}
    target_tag_ids = list(tag_id_to_name.keys())

    genome_pipeline = [
        {"$match": {"tagId": {"$in": target_tag_ids}, "relevance": {"$gt": 0.7}}},
        {"$group": {"_id": "$movieId", "matchedTags": {"$push": {"tagId": "$tagId", "relevance": "$relevance"}}}},
    ]

    total = add_stats(total, collect_stats(explain_aggregate(db, "ml_genome_scores", genome_pipeline)))
    genome_results = list(db.ml_genome_scores.aggregate(genome_pipeline, allowDiskUse=True))

    candidate_movie_ids = [result["_id"] for result in genome_results]

    ratings_pipeline = [
        {"$match": {"movieId": {"$in": candidate_movie_ids}}},
        {"$group": {"_id": "$movieId", "avgRating": {"$avg": "$rating"}, "ratingCount": {"$sum": 1}}},
        {"$match": {"avgRating": {"$gt": 4.0}, "ratingCount": {"$gte": 1000}}},
    ]

    total = add_stats(total, collect_stats(explain_aggregate(db, "ml_ratings", ratings_pipeline)))
    rating_results = list(db.ml_ratings.aggregate(ratings_pipeline, allowDiskUse=True))

    valid_movie_ids = [result["_id"] for result in rating_results]

    link_query = {"movieId": {"$in": valid_movie_ids}}
    link_projection = {"_id": 0, "movieId": 1, "tmdbId": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_links", link_query, link_projection)))
    links = list(db.ml_links.find(link_query, link_projection))

    tmdb_ids = [link.get("tmdbId") for link in links if link.get("tmdbId") is not None]

    metadata_query = {"id": {"$in": tmdb_ids}}
    metadata_projection = {"_id": 0, "id": 1, "title": 1, "release_year": 1, "genres": 1}

    credits_query = {"id": {"$in": tmdb_ids}}
    credits_projection = {"_id": 0, "id": 1, "directors": 1}

    total = add_stats(total, collect_stats(explain_find(db, "tmdb_movies_metadata", metadata_query, metadata_projection)))
    total = add_stats(total, collect_stats(explain_find(db, "tmdb_credits", credits_query, credits_projection)))

    return total


def v2_question_4(db):
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

    return collect_stats(explain_find(db, "movies_optimized", query, projection))


def v1_question_5(db):
    total = empty_stats()

    user_query = {"userId": USER_ID}
    user_projection = {"_id": 0, "movieId": 1, "rating": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_ratings", user_query, user_projection)))
    user_ratings = list(db.ml_ratings.find(user_query, user_projection))

    rated_movie_ids = {rating["movieId"] for rating in user_ratings}
    liked_movie_ids = [
        rating["movieId"]
        for rating in user_ratings
        if rating.get("rating", 0) >= MIN_USER_LIKED_RATING
    ]

    liked_movies_query = {"movieId": {"$in": liked_movie_ids}}
    liked_movies_projection = {"_id": 0, "movieId": 1, "title": 1, "genres": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_movies", liked_movies_query, liked_movies_projection)))
    liked_movies = list(db.ml_movies.find(liked_movies_query, liked_movies_projection))

    liked_links_query = {"movieId": {"$in": liked_movie_ids}}
    liked_links_projection = {"_id": 0, "movieId": 1, "tmdbId": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_links", liked_links_query, liked_links_projection)))
    liked_links = list(db.ml_links.find(liked_links_query, liked_links_projection))

    liked_movie_to_tmdb = {
        link["movieId"]: link.get("tmdbId")
        for link in liked_links
        if link.get("tmdbId") is not None
    }

    liked_tmdb_ids = list(liked_movie_to_tmdb.values())

    liked_credits_query = {"id": {"$in": liked_tmdb_ids}}
    liked_credits_projection = {"_id": 0, "id": 1, "cast": 1, "directors": 1}

    total = add_stats(total, collect_stats(explain_find(db, "tmdb_credits", liked_credits_query, liked_credits_projection)))
    liked_credits = list(db.tmdb_credits.find(liked_credits_query, liked_credits_projection))

    liked_movies_by_id = {movie["movieId"]: movie for movie in liked_movies}
    liked_credits_by_tmdb = {credits["id"]: credits for credits in liked_credits}

    liked_genres = set()
    liked_actors = set()
    liked_directors = set()

    for movie_id in liked_movie_ids:
        movie = liked_movies_by_id.get(movie_id)
        tmdb_id = liked_movie_to_tmdb.get(movie_id)
        credits = liked_credits_by_tmdb.get(tmdb_id)

        if not movie:
            continue

        liked_genres.update(split_genres(movie.get("genres")))
        liked_actors.update(get_top_cast_names(credits))
        liked_directors.update(get_director_names(credits))

    ratings_pipeline = [
        {"$group": {"_id": "$movieId", "avgRating": {"$avg": "$rating"}, "ratingCount": {"$sum": 1}}},
        {"$match": {"avgRating": {"$gt": MIN_AVG_RATING}, "ratingCount": {"$gte": MIN_RATING_COUNT}}},
    ]

    total = add_stats(total, collect_stats(explain_aggregate(db, "ml_ratings", ratings_pipeline)))
    rating_results = list(db.ml_ratings.aggregate(ratings_pipeline, allowDiskUse=True))

    rating_stats = {
        result["_id"]: {
            "avgRating": result["avgRating"],
            "ratingCount": result["ratingCount"],
        }
        for result in rating_results
        if result["_id"] not in rated_movie_ids
    }

    candidate_movie_ids = list(rating_stats.keys())

    candidate_movies_query = {"movieId": {"$in": candidate_movie_ids}}
    candidate_movies_projection = {"_id": 0, "movieId": 1, "title": 1, "genres": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_movies", candidate_movies_query, candidate_movies_projection)))
    candidate_movies = list(db.ml_movies.find(candidate_movies_query, candidate_movies_projection))

    candidate_links_query = {"movieId": {"$in": candidate_movie_ids}}
    candidate_links_projection = {"_id": 0, "movieId": 1, "tmdbId": 1}

    total = add_stats(total, collect_stats(explain_find(db, "ml_links", candidate_links_query, candidate_links_projection)))
    candidate_links = list(db.ml_links.find(candidate_links_query, candidate_links_projection))

    candidate_movie_to_tmdb = {
        link["movieId"]: link.get("tmdbId")
        for link in candidate_links
        if link.get("tmdbId") is not None
    }

    candidate_tmdb_ids = list(set(candidate_movie_to_tmdb.values()))

    candidate_metadata_query = {"id": {"$in": candidate_tmdb_ids}}
    candidate_metadata_projection = {"_id": 0, "id": 1, "title": 1, "release_year": 1, "popularity": 1, "budget": 1, "revenue": 1}

    candidate_credits_query = {"id": {"$in": candidate_tmdb_ids}}
    candidate_credits_projection = {"_id": 0, "id": 1, "cast": 1, "directors": 1}

    total = add_stats(total, collect_stats(explain_find(db, "tmdb_movies_metadata", candidate_metadata_query, candidate_metadata_projection)))
    total = add_stats(total, collect_stats(explain_find(db, "tmdb_credits", candidate_credits_query, candidate_credits_projection)))

    return total


def v2_question_5(db):
    total = empty_stats()

    user_query = {"userId": USER_ID}
    user_projection = {"_id": 0}

    total = add_stats(total, collect_stats(explain_find(db, "user_profiles_optimized", user_query, user_projection)))
    user_profile = db.user_profiles_optimized.find_one(user_query, user_projection)

    rated_movie_ids = user_profile.get("ratedMovieIds", [])
    liked_movie_ids = user_profile.get("likedMovieIds", [])
    liked_genres = set(user_profile.get("likedGenres", {}).get("ml", []))
    liked_actors = set(user_profile.get("likedActors", {}).get("top", []))
    liked_directors = set(user_profile.get("likedDirectors", []))

    liked_movies_query = {"movieId": {"$in": liked_movie_ids}}
    liked_movies_projection = {"_id": 0, "movieId": 1, "title": 1, "releaseYear": 1, "genres.ml": 1, "people.topCastNames": 1, "people.directors": 1}

    total = add_stats(total, collect_stats(explain_find(db, "movies_optimized", liked_movies_query, liked_movies_projection)))

    candidate_query = {
        "movieId": {"$nin": rated_movie_ids},
        "ratingStats.avgRating": {"$gt": MIN_AVG_RATING},
        "ratingStats.ratingCount": {"$gte": MIN_RATING_COUNT},
        "genres.ml": {"$in": list(liked_genres)},
        "$or": [
            {"people.topCastNames": {"$in": list(liked_actors)}},
            {"people.directors": {"$in": list(liked_directors)}},
        ],
    }

    candidate_projection = {
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

    total = add_stats(total, collect_stats(explain_find(db, "movies_optimized", candidate_query, candidate_projection)))

    return total


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def create_chart(rows: list[dict[str, Any]]) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    labels = [f"Pitanje {row['question']}" for row in rows]
    v1_values = [max(row["v1_docs_examined"], 1) for row in rows]
    v2_values = [max(row["v2_docs_examined"], 1) for row in rows]

    x = range(len(labels))
    width = 0.35

    plt.figure(figsize=(12, 7))
    plt.bar([i - width / 2 for i in x], v1_values, width=width, label="V1 - pregledani dokumenti")
    plt.bar([i + width / 2 for i in x], v2_values, width=width, label="V2 - pregledani dokumenti")

    plt.yscale("log")
    plt.title("Broj pregledanih dokumenata po upitu: V1 vs V2")
    plt.xlabel("Analitičko pitanje")
    plt.ylabel("totalDocsExamined - log skala")
    plt.xticks(list(x), labels)
    plt.legend()

    for i, value in enumerate(v1_values):
        plt.text(i - width / 2, value, format_number(value), ha="center", va="bottom", fontsize=8)

    for i, value in enumerate(v2_values):
        plt.text(i + width / 2, value, format_number(value), ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(OUTPUT_CHART, dpi=180, bbox_inches="tight")
    plt.close()


def write_outputs(rows: list[dict[str, Any]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    csv_lines = [
        "question,v1_docs_examined,v2_docs_examined,v1_keys_examined,v2_keys_examined,v1_n_returned,v2_n_returned,doc_reduction"
    ]

    txt_lines = [
        "PREGLEDANI DOKUMENTI PO UPITU - V1 VS V2",
        "=" * 80,
        "Mjera: totalDocsExamined iz MongoDB explain('executionStats') plana.",
        "Napomena: kod upita koji imaju više faza rezultat je zbir explain vrijednosti za glavne operacije.",
        "",
    ]

    for row in rows:
        reduction = (
            row["v1_docs_examined"] / row["v2_docs_examined"]
            if row["v2_docs_examined"] > 0
            else 0
        )

        csv_lines.append(
            f"{row['question']},{row['v1_docs_examined']},{row['v2_docs_examined']},"
            f"{row['v1_keys_examined']},{row['v2_keys_examined']},"
            f"{row['v1_n_returned']},{row['v2_n_returned']},{reduction:.2f}"
        )

        txt_lines.append(
            f"Pitanje {row['question']}: "
            f"V1 pregledano {format_number(row['v1_docs_examined'])} dokumenata, "
            f"V2 pregledano {format_number(row['v2_docs_examined'])} dokumenata, "
            f"smanjenje {reduction:.2f}x"
        )

    OUTPUT_CSV.write_text("\n".join(csv_lines), encoding="utf-8")
    OUTPUT_TXT.write_text("\n".join(txt_lines), encoding="utf-8")


def main() -> None:
    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    question_functions = {
        1: (v1_question_1, v2_question_1),
        2: (v1_question_2, v2_question_2),
        3: (v1_question_3, v2_question_3),
        4: (v1_question_4, v2_question_4),
        5: (v1_question_5, v2_question_5),
    }

    rows = []

    for question, (v1_function, v2_function) in question_functions.items():
        print(f"Racunam explain statistiku za pitanje {question}...")

        v1_stats = v1_function(db)
        v2_stats = v2_function(db)

        rows.append({
            "question": question,
            "v1_docs_examined": v1_stats["docsExamined"],
            "v2_docs_examined": v2_stats["docsExamined"],
            "v1_keys_examined": v1_stats["keysExamined"],
            "v2_keys_examined": v2_stats["keysExamined"],
            "v1_n_returned": v1_stats["nReturned"],
            "v2_n_returned": v2_stats["nReturned"],
        })

    write_outputs(rows)
    create_chart(rows)

    print("")
    print("Gotovo.")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"TXT: {OUTPUT_TXT}")
    print(f"Graf: {OUTPUT_CHART}")


if __name__ == "__main__":
    main()