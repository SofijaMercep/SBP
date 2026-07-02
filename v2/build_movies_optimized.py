from datetime import datetime
from pathlib import Path
import ast
import re

from pymongo import ASCENDING, DESCENDING, MongoClient


DB_NAME = "movie_recommendation_db"
USER_ID = 123

OUTPUT_FILE = Path("v2/results/build_v2_summary.txt")

GENOME_RELEVANCE_THRESHOLD = 0.7
PRINCIPAL_CAST_LIMIT = 10
TOP_CAST_LIMIT = 3
BATCH_SIZE = 1000


def get_int(value, default=None):
    if value is None or value == "":
        return default

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_float(value, default=None):
    if value is None or value == "":
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_possible_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        try:
            parsed = ast.literal_eval(value)

            if isinstance(parsed, list):
                return parsed

            return []
        except Exception:
            return []

    return []


def extract_names(value):
    items = parse_possible_list(value)
    names = []

    for item in items:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            name = ""

        if name:
            names.append(name)

    return sorted(set(names))


def split_movielens_genres(value):
    if not value:
        return []

    if value == "(no genres listed)":
        return []

    return sorted({
        genre.strip()
        for genre in str(value).split("|")
        if genre.strip()
    })


def extract_release_year_from_title(title):
    if not title:
        return None

    match = re.search(r"\((\d{4})\)", str(title))

    if not match:
        return None

    return get_int(match.group(1))


def get_release_decade(year):
    if year is None:
        return None

    return (year // 10) * 10


def rating_bucket(avg_rating):
    if avg_rating is None:
        return "unknown"

    if avg_rating >= 4.3:
        return "excellent"

    if avg_rating >= 4.0:
        return "very_good"

    if avg_rating >= 3.5:
        return "good"

    if avg_rating >= 3.0:
        return "average"

    return "low"


def rating_count_bucket(count):
    if count is None or count == 0:
        return "none"

    if count >= 10000:
        return "mass"

    if count >= 5000:
        return "very_high"

    if count >= 1000:
        return "high"

    if count >= 100:
        return "medium"

    return "low"


def money_bucket(value):
    if value is None or value <= 0:
        return "unknown"

    if value >= 150_000_000:
        return "blockbuster"

    if value >= 50_000_000:
        return "high"

    if value >= 10_000_000:
        return "medium"

    return "low"


def popularity_bucket(value):
    if value is None:
        return "unknown"

    if value >= 30:
        return "very_high"

    if value >= 15:
        return "high"

    if value >= 5:
        return "medium"

    return "low"


def profit_status(budget, revenue):
    if budget is None or revenue is None or budget <= 0 or revenue <= 0:
        return "unknown"

    if revenue > budget:
        return "profitable"

    if revenue == budget:
        return "break_even"

    return "not_profitable"


def profit_bucket(profit):
    if profit is None:
        return "unknown"

    if profit >= 300_000_000:
        return "very_high_profit"

    if profit >= 50_000_000:
        return "high_profit"

    if profit >= 0:
        return "profit"

    if profit <= -50_000_000:
        return "large_loss"

    return "loss"


def build_rating_stats(db):
    print("1/8 Racunam rating statistiku po filmu...")

    pipeline = [
        {
            "$group": {
                "_id": "$movieId",
                "avgRating": {"$avg": "$rating"},
                "ratingCount": {"$sum": 1},
                "highRatingCount": {
                    "$sum": {
                        "$cond": [
                            {"$gte": ["$rating", 4.5]},
                            1,
                            0
                        ]
                    }
                },
            }
        }
    ]

    rating_stats = {}

    for row in db.ml_ratings.aggregate(pipeline, allowDiskUse=True):
        movie_id = get_int(row["_id"])

        if movie_id is None:
            continue

        avg_rating = get_float(row.get("avgRating"))
        rating_count = get_int(row.get("ratingCount"), 0)
        high_rating_count = get_int(row.get("highRatingCount"), 0)

        rating_stats[movie_id] = {
            "avgRating": avg_rating,
            "ratingCount": rating_count,
            "highRatingCount": high_rating_count,
            "highRatingShare": (
                high_rating_count / rating_count
                if rating_count > 0
                else 0
            ),
            "ratingBucket": rating_bucket(avg_rating),
            "ratingCountBucket": rating_count_bucket(rating_count),
        }

    print(f"   Rating statistika izracunata za {len(rating_stats)} filmova.")
    return rating_stats


def load_movielens_movies(db):
    print("2/8 Ucitavam MovieLens filmove...")

    movies = {}

    for movie in db.ml_movies.find({}, {"_id": 0}):
        movie_id = get_int(movie.get("movieId"))

        if movie_id is None:
            continue

        movies[movie_id] = movie

    print(f"   Ucitano MovieLens filmova: {len(movies)}")
    return movies


def load_links(db):
    print("3/8 Ucitavam veze MovieLens -> TMDB...")

    links = {}

    for link in db.ml_links.find({}, {"_id": 0}):
        movie_id = get_int(link.get("movieId"))

        if movie_id is None:
            continue

        links[movie_id] = {
            "tmdbId": get_int(link.get("tmdbId")),
            "imdbId": get_int(link.get("imdbId")),
        }

    print(f"   Ucitano linkova: {len(links)}")
    return links


def load_tmdb_metadata(db):
    print("4/8 Ucitavam TMDB metadata...")

    metadata_by_tmdb_id = {}

    for metadata in db.tmdb_movies_metadata.find({}, {"_id": 0}):
        tmdb_id = get_int(metadata.get("id"))

        if tmdb_id is None:
            continue

        metadata_by_tmdb_id[tmdb_id] = metadata

    print(f"   Ucitano TMDB metadata dokumenata: {len(metadata_by_tmdb_id)}")
    return metadata_by_tmdb_id


def normalize_cast_member(member, fallback_order):
    if not isinstance(member, dict):
        return None

    name = str(member.get("name", "")).strip()

    if not name:
        return None

    order = get_int(member.get("order"), fallback_order)

    return {
        "id": get_int(member.get("id")),
        "name": name,
        "character": member.get("character"),
        "order": order,
    }


def load_tmdb_credits(db):
    print("5/8 Ucitavam TMDB credits, glumce i rezisere...")

    credits_by_tmdb_id = {}

    for credit in db.tmdb_credits.find({}, {"_id": 0}):
        tmdb_id = get_int(credit.get("id"))

        if tmdb_id is None:
            continue

        raw_cast = parse_possible_list(credit.get("cast"))
        normalized_cast = []

        for index, member in enumerate(raw_cast):
            normalized_member = normalize_cast_member(member, index)

            if normalized_member:
                normalized_cast.append(normalized_member)

        normalized_cast.sort(key=lambda item: item["order"])

        principal_cast = normalized_cast[:PRINCIPAL_CAST_LIMIT]
        top_cast = normalized_cast[:TOP_CAST_LIMIT]

        directors = []

        if credit.get("directors"):
            directors = extract_names(credit.get("directors"))
        else:
            raw_crew = parse_possible_list(credit.get("crew"))

            for crew_member in raw_crew:
                if not isinstance(crew_member, dict):
                    continue

                if crew_member.get("job") == "Director":
                    name = str(crew_member.get("name", "")).strip()

                    if name:
                        directors.append(name)

            directors = sorted(set(directors))

        credits_by_tmdb_id[tmdb_id] = {
            "castCount": len(normalized_cast),
            "principalCast": principal_cast,
            "principalCastNames": [member["name"] for member in principal_cast],
            "topCast": top_cast,
            "topCastNames": [member["name"] for member in top_cast],
            "directors": directors,
        }

    print(f"   Ucitano credits dokumenata: {len(credits_by_tmdb_id)}")
    return credits_by_tmdb_id


def load_high_relevance_genome_tags(db):
    print("6/8 Izdvajam opste relevantne genome tagove...")

    tag_names_by_id = {}

    for tag in db.ml_genome_tags.find({}, {"_id": 0}):
        tag_id = get_int(tag.get("tagId"))
        tag_name = str(tag.get("tag", "")).strip()

        if tag_id is not None and tag_name:
            tag_names_by_id[tag_id] = tag_name

    high_tags_by_movie = {}

    cursor = db.ml_genome_scores.find(
        {"relevance": {"$gt": GENOME_RELEVANCE_THRESHOLD}},
        {"_id": 0, "movieId": 1, "tagId": 1, "relevance": 1},
        no_cursor_timeout=True,
    ).batch_size(5000)

    processed = 0

    try:
        for row in cursor:
            movie_id = get_int(row.get("movieId"))
            tag_id = get_int(row.get("tagId"))
            relevance = get_float(row.get("relevance"))

            if movie_id is None or tag_id is None or relevance is None:
                continue

            tag_name = tag_names_by_id.get(tag_id)

            if not tag_name:
                continue

            if movie_id not in high_tags_by_movie:
                high_tags_by_movie[movie_id] = []

            high_tags_by_movie[movie_id].append({
                "tagId": tag_id,
                "tag": tag_name,
                "relevance": relevance,
            })

            processed += 1

            if processed % 500000 == 0:
                print(f"   Obradjeno high relevance genome score zapisa: {processed}")
    finally:
        cursor.close()

    for movie_id, tags in high_tags_by_movie.items():
        tags.sort(key=lambda item: item["relevance"], reverse=True)

    print(f"   Filmova sa relevantnim genome tagovima: {len(high_tags_by_movie)}")
    print(f"   Relevantnih genome score zapisa: {processed}")
    return high_tags_by_movie


def build_movie_document(movie_id, ml_movie, link, metadata, credits, rating_stats, genome_tags):
    movie_lens_title = ml_movie.get("title")
    tmdb_title = metadata.get("title") if metadata else None

    release_year = (
        get_int(metadata.get("release_year")) if metadata else None
    )

    if release_year is None:
        release_year = extract_release_year_from_title(movie_lens_title)

    ml_genres = split_movielens_genres(ml_movie.get("genres"))
    tmdb_genres = extract_names(metadata.get("genres")) if metadata else []
    all_genres = sorted(set(ml_genres + tmdb_genres))

    budget = get_int(metadata.get("budget"), 0) if metadata else 0
    revenue = get_int(metadata.get("revenue"), 0) if metadata else 0
    popularity = get_float(metadata.get("popularity")) if metadata else None

    vote_average = (
        get_float(metadata.get("vote_average"))
        if metadata
        else None
    )

    if vote_average is None and metadata:
        vote_average = get_float(metadata.get("voteAverage"))

    vote_count = (
        get_int(metadata.get("vote_count"))
        if metadata
        else None
    )

    if vote_count is None and metadata:
        vote_count = get_int(metadata.get("voteCount"))

    runtime = get_float(metadata.get("runtime")) if metadata else None

    profit = None
    revenue_budget_ratio = None

    if budget and revenue and budget > 0:
        profit = revenue - budget
        revenue_budget_ratio = revenue / budget

    status = profit_status(budget, revenue)

    sorted_genome_tags = genome_tags or []
    high_relevance_tag_names = sorted({
        tag["tag"]
        for tag in sorted_genome_tags
        if tag.get("tag")
    })

    return {
        "movieId": movie_id,
        "tmdbId": link.get("tmdbId") if link else None,
        "imdbId": link.get("imdbId") if link else None,

        "title": tmdb_title or movie_lens_title,
        "movieLensTitle": movie_lens_title,
        "tmdbTitle": tmdb_title,

        "releaseYear": release_year,
        "releaseDecade": get_release_decade(release_year),

        "genres": {
            "ml": ml_genres,
            "tmdb": tmdb_genres,
            "all": all_genres,
        },

        "ratingStats": rating_stats,

        "commercial": {
            "budget": budget,
            "revenue": revenue,
            "profit": profit,
            "profitStatus": status,
            "revenueBudgetRatio": revenue_budget_ratio,
            "revenueGreaterThanBudget": status == "profitable",
            "budgetGreaterThanRevenue": status == "not_profitable",
            "popularity": popularity,
            "voteAverage": vote_average,
            "voteCount": vote_count,
            "runtime": runtime,
        },

        "people": {
            "castCount": credits.get("castCount", 0) if credits else 0,
            "principalCast": credits.get("principalCast", []) if credits else [],
            "principalCastNames": credits.get("principalCastNames", []) if credits else [],
            "topCast": credits.get("topCast", []) if credits else [],
            "topCastNames": credits.get("topCastNames", []) if credits else [],
            "directors": credits.get("directors", []) if credits else [],
        },

        "genome": {
            "highRelevanceTags": sorted_genome_tags,
            "highRelevanceTagNames": high_relevance_tag_names,
            "topGenomeTags": sorted_genome_tags[:20],
        },

        "buckets": {
            "ratingBucket": rating_stats.get("ratingBucket"),
            "ratingCountBucket": rating_stats.get("ratingCountBucket"),
            "budgetBucket": money_bucket(budget),
            "revenueBucket": money_bucket(revenue),
            "popularityBucket": popularity_bucket(popularity),
            "profitBucket": profit_bucket(profit),
        },
    }


def create_movies_optimized(db, rating_stats, ml_movies, links, metadata_by_tmdb_id, credits_by_tmdb_id, genome_by_movie):
    print("7/8 Kreiram movies_optimized dokumente...")

    movies_optimized = db.movies_optimized
    movies_optimized.drop()

    batch = []
    inserted = 0
    skipped_without_rating = 0

    for movie_id, ml_movie in ml_movies.items():
        stats = rating_stats.get(movie_id)

        if not stats:
            skipped_without_rating += 1
            continue

        link = links.get(movie_id, {})
        tmdb_id = link.get("tmdbId")

        metadata = metadata_by_tmdb_id.get(tmdb_id) if tmdb_id else None
        credits = credits_by_tmdb_id.get(tmdb_id) if tmdb_id else None
        genome_tags = genome_by_movie.get(movie_id, [])

        document = build_movie_document(
            movie_id=movie_id,
            ml_movie=ml_movie,
            link=link,
            metadata=metadata,
            credits=credits,
            rating_stats=stats,
            genome_tags=genome_tags,
        )

        batch.append(document)

        if len(batch) >= BATCH_SIZE:
            movies_optimized.insert_many(batch)
            inserted += len(batch)
            batch = []
            print(f"   Insertovano: {inserted}")

    if batch:
        movies_optimized.insert_many(batch)
        inserted += len(batch)

    print(f"   movies_optimized insertovano: {inserted}")
    print(f"   Filmova bez rating statistike preskoceno: {skipped_without_rating}")

    return inserted, skipped_without_rating


def create_user_profiles_optimized(db):
    print("8/8 Kreiram user_profiles_optimized za vise korisnika...")

    user_profiles = db.user_profiles_optimized
    user_profiles.drop()

    min_liked_movies = 3

    movie_profile_index = {}

    for movie in db.movies_optimized.find(
        {},
        {
            "_id": 0,
            "movieId": 1,
            "title": 1,
            "genres.ml": 1,
            "genres.all": 1,
            "people.principalCastNames": 1,
            "people.topCastNames": 1,
            "people.directors": 1,
        }
    ):
        movie_id = get_int(movie.get("movieId"))

        if movie_id is None:
            continue

        genres = movie.get("genres", {})
        people = movie.get("people", {})

        movie_profile_index[movie_id] = {
            "mlGenres": genres.get("ml", []),
            "allGenres": genres.get("all", []),
            "principalActors": people.get("principalCastNames", []),
            "topActors": people.get("topCastNames", []),
            "directors": people.get("directors", []),
        }

    users_cursor = db.ml_ratings.aggregate(
        [
            {
                "$group": {
                    "_id": "$userId",
                    "ratingCount": {"$sum": 1},
                    "likedRatingCount": {
                        "$sum": {
                            "$cond": [
                                {"$gte": ["$rating", 4.5]},
                                1,
                                0
                            ]
                        }
                    },
                    "ratedMovieIds": {"$push": "$movieId"},
                    "likedMovieIdsWithNulls": {
                        "$push": {
                            "$cond": [
                                {"$gte": ["$rating", 4.5]},
                                "$movieId",
                                None
                            ]
                        }
                    }
                }
            },
            {
                "$match": {
                    "likedRatingCount": {"$gte": min_liked_movies}
                }
            }
        ],
        allowDiskUse=True
    )

    inserted = 0
    skipped = 0
    batch = []

    for user in users_cursor:
        user_id = get_int(user.get("_id"))

        if user_id is None:
            skipped += 1
            continue

        rated_movie_ids = [
            get_int(movie_id)
            for movie_id in user.get("ratedMovieIds", [])
            if get_int(movie_id) is not None
        ]

        liked_movie_ids = [
            get_int(movie_id)
            for movie_id in user.get("likedMovieIdsWithNulls", [])
            if get_int(movie_id) is not None
        ]

        if len(liked_movie_ids) < min_liked_movies:
            skipped += 1
            continue

        liked_ml_genres = set()
        liked_all_genres = set()
        liked_principal_actors = set()
        liked_top_actors = set()
        liked_directors = set()

        matched_liked_movies = 0

        for movie_id in liked_movie_ids:
            movie_profile = movie_profile_index.get(movie_id)

            if not movie_profile:
                continue

            matched_liked_movies += 1
            liked_ml_genres.update(movie_profile["mlGenres"])
            liked_all_genres.update(movie_profile["allGenres"])
            liked_principal_actors.update(movie_profile["principalActors"])
            liked_top_actors.update(movie_profile["topActors"])
            liked_directors.update(movie_profile["directors"])

        if matched_liked_movies < min_liked_movies:
            skipped += 1
            continue

        batch.append({
            "userId": user_id,
            "ratingCount": len(rated_movie_ids),
            "ratedMovieIds": rated_movie_ids,
            "likedMovieIds": liked_movie_ids,
            "likedMovieCount": len(liked_movie_ids),
            "matchedLikedMovieCount": matched_liked_movies,
            "likedGenres": {
                "ml": sorted(liked_ml_genres),
                "all": sorted(liked_all_genres),
            },
            "likedActors": {
                "principal": sorted(liked_principal_actors),
                "top": sorted(liked_top_actors),
            },
            "likedDirectors": sorted(liked_directors),
        })

        if len(batch) >= 500:
            user_profiles.insert_many(batch)
            inserted += len(batch)
            batch = []

    if batch:
        user_profiles.insert_many(batch)
        inserted += len(batch)

    print(f"   user_profiles_optimized insertovano: {inserted}")
    print(f"   Korisnickih profila preskoceno: {skipped}")


def create_indexes(db):
    print("Kreiram indekse za v2 semu...")

    movies = db.movies_optimized
    users = db.user_profiles_optimized

    movies.create_index([("movieId", ASCENDING)], unique=True, name="idx_movie_id")
    movies.create_index([("tmdbId", ASCENDING)], name="idx_tmdb_id")
    movies.create_index([("releaseYear", ASCENDING)], name="idx_release_year")
    movies.create_index([("releaseDecade", ASCENDING)], name="idx_release_decade")

    movies.create_index([("genres.ml", ASCENDING)], name="idx_genres_ml")
    movies.create_index([("genres.tmdb", ASCENDING)], name="idx_genres_tmdb")
    movies.create_index([("genres.all", ASCENDING)], name="idx_genres_all")

    movies.create_index(
        [
            ("ratingStats.avgRating", DESCENDING),
            ("ratingStats.ratingCount", DESCENDING),
        ],
        name="idx_rating_avg_count"
    )

    movies.create_index(
        [
            ("commercial.profitStatus", ASCENDING),
            ("ratingStats.avgRating", DESCENDING),
            ("ratingStats.ratingCount", DESCENDING),
        ],
        name="idx_profit_rating"
    )

    movies.create_index([("commercial.budget", ASCENDING)], name="idx_budget")
    movies.create_index([("commercial.revenue", ASCENDING)], name="idx_revenue")
    movies.create_index([("commercial.popularity", ASCENDING)], name="idx_popularity")

    movies.create_index([("people.principalCastNames", ASCENDING)], name="idx_principal_cast_names")
    movies.create_index([("people.topCastNames", ASCENDING)], name="idx_top_cast_names")
    movies.create_index([("people.directors", ASCENDING)], name="idx_directors")

    movies.create_index([("genome.highRelevanceTagNames", ASCENDING)], name="idx_high_relevance_tag_names")

    movies.create_index([("buckets.ratingBucket", ASCENDING)], name="idx_rating_bucket")
    movies.create_index([("buckets.ratingCountBucket", ASCENDING)], name="idx_rating_count_bucket")
    movies.create_index([("buckets.budgetBucket", ASCENDING)], name="idx_budget_bucket")
    movies.create_index([("buckets.revenueBucket", ASCENDING)], name="idx_revenue_bucket")
    movies.create_index([("buckets.popularityBucket", ASCENDING)], name="idx_popularity_bucket")
    movies.create_index([("buckets.profitBucket", ASCENDING)], name="idx_profit_bucket")

    users.create_index([("userId", ASCENDING)], unique=True, name="idx_user_id")

    print("   Indeksi kreirani.")


def write_summary(start_time, db, inserted_count, skipped_count):
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    lines = []
    lines.append("V2 BUILD SUMMARY - REORGANIZOVANA OPTIMIZOVANA SEMA")
    lines.append("=" * 70)
    lines.append(f"Ukupno vrijeme izgradnje v2: {duration:.3f} sekundi")
    lines.append(f"movies_optimized count: {db.movies_optimized.count_documents({})}")
    lines.append(f"user_profiles_optimized count: {db.user_profiles_optimized.count_documents({})}")
    lines.append(f"Insertovano filmova: {inserted_count}")
    lines.append(f"Preskoceno filmova bez rating statistike: {skipped_count}")
    lines.append("")
    lines.append("Opis optimizacije:")
    lines.append(
        "V2 sema je reorganizovana oko dokumenta filma. Umjesto razdvojenih sirovih kolekcija, "
        "kolekcija movies_optimized cuva osnovne podatke, zanrove, rating statistiku, komercijalne podatke, "
        "glumce, rezisere, genome tagove i bucket kategorije u jednom dokumentu."
    )
    lines.append(
        "Kolekcija user_profiles_optimized cuva unaprijed pripremljen profil korisnika za potrebe preporuka."
    )

    output = "\n".join(lines)
    print("")
    print(output)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")


def main():
    start_time = datetime.now()

    print("Kreiranje nove v2 optimizovane seme pocinje...")
    print("Ova verzija nije prilagodjena samo konkretnim pitanjima, nego opstem modelu filmske analitike.")
    print("")

    client = MongoClient("mongodb://localhost:27017")
    db = client[DB_NAME]

    rating_stats = build_rating_stats(db)
    ml_movies = load_movielens_movies(db)
    links = load_links(db)
    metadata_by_tmdb_id = load_tmdb_metadata(db)
    credits_by_tmdb_id = load_tmdb_credits(db)
    genome_by_movie = load_high_relevance_genome_tags(db)

    inserted_count, skipped_count = create_movies_optimized(
        db=db,
        rating_stats=rating_stats,
        ml_movies=ml_movies,
        links=links,
        metadata_by_tmdb_id=metadata_by_tmdb_id,
        credits_by_tmdb_id=credits_by_tmdb_id,
        genome_by_movie=genome_by_movie,
    )

    create_user_profiles_optimized(db)
    create_indexes(db)
    write_summary(start_time, db, inserted_count, skipped_count)

    print("")
    print("Nova v2 optimizovana sema je napravljena.")


if __name__ == "__main__":
    main()