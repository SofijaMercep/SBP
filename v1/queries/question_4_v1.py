from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"
OUTPUT_FILE = Path("v1/results/question_4_v1_results.txt")


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

    print("Pokrecem v1 upit za pitanje 4...")
    print("Ovo moze trajati duze jer se radi nad neoptimizovanom semom.")

    start_time = datetime.now()

    # 1. Pronalazimo konkretne genome tagove koje pitanje koristi.
    tag_documents = list(db.ml_genome_tags.find(
        {"tag": {"$in": TARGET_TAGS}},
        {"_id": 0, "tagId": 1, "tag": 1}
    ))

    tag_id_to_name = {
        tag_document["tagId"]: tag_document["tag"]
        for tag_document in tag_documents
    }

    target_tag_ids = list(tag_id_to_name.keys())

    if not target_tag_ids:
        print("Nije pronadjen nijedan trazeni genome tag.")
        return

    # 2. Iz genome_scores izdvajamo filmove kod kojih je neki od trazenih tagova relevantan preko 0.7.
    genome_pipeline = [
        {
            "$match": {
                "tagId": {"$in": target_tag_ids},
                "relevance": {"$gt": 0.7}
            }
        },
        {
            "$group": {
                "_id": "$movieId",
                "matchedTags": {
                    "$push": {
                        "tagId": "$tagId",
                        "relevance": "$relevance"
                    }
                }
            }
        }
    ]

    genome_results = list(db.ml_genome_scores.aggregate(
        genome_pipeline,
        allowDiskUse=True
    ))

    movie_tags = {}

    for result in genome_results:
        movie_id = result["_id"]
        tags = []

        for tag_info in result.get("matchedTags", []):
            tag_id = tag_info.get("tagId")
            tag_name = tag_id_to_name.get(tag_id)

            if tag_name is None:
                continue

            tags.append({
                "tag": tag_name,
                "relevance": tag_info.get("relevance")
            })

        movie_tags[movie_id] = tags

    candidate_movie_ids = list(movie_tags.keys())

    if not candidate_movie_ids:
        print("Nema filmova koji imaju trazene genome tagove sa relevantnoscu vecom od 0.7.")
        return

    # 3. Nad MovieLens ratings kolekcijom racunamo prosjecnu ocjenu i broj ocjena za te filmove.
    ratings_pipeline = [
        {
            "$match": {
                "movieId": {"$in": candidate_movie_ids}
            }
        },
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
        }
    ]

    rating_results = list(db.ml_ratings.aggregate(
        ratings_pipeline,
        allowDiskUse=True
    ))

    rating_stats = {
        result["_id"]: {
            "avgRating": result["avgRating"],
            "ratingCount": result["ratingCount"]
        }
        for result in rating_results
    }

    valid_movie_ids = list(rating_stats.keys())

    if not valid_movie_ids:
        print("Nema filmova koji zadovoljavaju uslove za ocjenu i broj ocjena.")
        return

    # 4. Povezujemo MovieLens filmove sa TMDB podacima preko ml_links.
    links = list(db.ml_links.find(
        {"movieId": {"$in": valid_movie_ids}},
        {"_id": 0, "movieId": 1, "tmdbId": 1}
    ))

    movie_id_to_tmdb_id = {
        link["movieId"]: link.get("tmdbId")
        for link in links
        if link.get("tmdbId") is not None
    }

    tmdb_ids = list(movie_id_to_tmdb_id.values())

    metadata_documents = list(db.tmdb_movies_metadata.find(
        {"id": {"$in": tmdb_ids}},
        {
            "_id": 0,
            "id": 1,
            "title": 1,
            "release_year": 1,
            "genres": 1
        }
    ))

    credits_documents = list(db.tmdb_credits.find(
        {"id": {"$in": tmdb_ids}},
        {
            "_id": 0,
            "id": 1,
            "directors": 1
        }
    ))

    metadata_by_tmdb_id = {
        metadata["id"]: metadata
        for metadata in metadata_documents
    }

    credits_by_tmdb_id = {
        credits["id"]: credits
        for credits in credits_documents
    }

    # 5. Grupisemo filmove po reziseru.
    directors = {}

    for movie_id in valid_movie_ids:
        tmdb_id = movie_id_to_tmdb_id.get(movie_id)

        if tmdb_id is None:
            continue

        metadata = metadata_by_tmdb_id.get(tmdb_id)
        credits = credits_by_tmdb_id.get(tmdb_id)

        if not metadata or not credits:
            continue

        movie_directors = credits.get("directors", [])

        if not movie_directors:
            continue

        stats = rating_stats[movie_id]

        movie_info = {
            "movieId": movie_id,
            "tmdbId": tmdb_id,
            "title": metadata.get("title"),
            "releaseYear": metadata.get("release_year"),
            "genres": metadata.get("genres", []),
            "avgRating": stats["avgRating"],
            "ratingCount": stats["ratingCount"],
            "matchedTags": movie_tags.get(movie_id, [])
        }

        for director in movie_directors:
            director_name = director.get("name")

            if not director_name:
                continue

            if director_name not in directors:
                directors[director_name] = {
                    "director": director_name,
                    "movies": {}
                }

            directors[director_name]["movies"][movie_id] = movie_info

    # 6. Zadrzavamo samo rezisere sa najmanje 3 filma.
    results = []

    for director_data in directors.values():
        movies = list(director_data["movies"].values())

        if len(movies) < 3:
            continue

        avg_director_rating = sum(movie["avgRating"] for movie in movies) / len(movies)
        total_ratings = sum(movie["ratingCount"] for movie in movies)

        results.append({
            "director": director_data["director"],
            "movieCount": len(movies),
            "avgDirectorRating": avg_director_rating,
            "totalRatings": total_ratings,
            "movies": movies
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
    lines.append("PITANJE 4 - V1 / NEOPTIMIZOVANA SEMA")
    lines.append("=" * 60)
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