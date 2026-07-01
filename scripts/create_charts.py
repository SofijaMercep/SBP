from pathlib import Path
import csv
import re

import matplotlib.pyplot as plt
from pymongo import MongoClient


DB_NAME = "movie_recommendation_db"

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

V1_SUMMARY_CSV = ROOT_DIR / "v1" / "results" / "v1_summary.csv"
V2_SUMMARY_CSV = ROOT_DIR / "v2" / "results" / "v2_summary.csv"
FINAL_COMPARISON_TXT = RESULTS_DIR / "final_comparison.txt"

CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def save_chart(filename: str) -> None:
    path = CHARTS_DIR / filename
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()

    # Kopija u root folder, da ostane kao u prethodnoj strukturi projekta.
    root_copy = ROOT_DIR / filename
    if filename in {"broj_dokumenata.png", "vrijeme_izvrsavanja.png"}:
        root_copy.write_bytes(path.read_bytes())

    print(f"Generated: {path}")


def read_summary_csv(path: Path) -> dict[int, dict[str, float]]:
    rows = {}

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            question_number = extract_question_number(row)
            if question_number is None:
                continue

            rows[question_number] = {
                "time": extract_float(row),
                "count": extract_int(row),
            }

    return rows


def extract_question_number(row: dict[str, str]) -> int | None:
    joined = " ".join(str(value) for value in row.values())
    match = re.search(r"(\d+)", joined)

    if not match:
        return None

    return int(match.group(1))


def extract_float(row: dict[str, str]) -> float:
    for value in row.values():
        text = str(value).replace(",", ".")
        match = re.search(r"(\d+(?:\.\d+)?)", text)

        if match and ("sek" in text.lower() or "." in match.group(1)):
            return float(match.group(1))

    numeric_values = []

    for value in row.values():
        text = str(value).replace(",", ".")
        match = re.search(r"(\d+(?:\.\d+)?)", text)

        if match:
            numeric_values.append(float(match.group(1)))

    return numeric_values[1] if len(numeric_values) > 1 else 0.0


def extract_int(row: dict[str, str]) -> int:
    values = []

    for value in row.values():
        text = str(value)
        matches = re.findall(r"\d+", text)
        values.extend(int(match) for match in matches)

    return values[-1] if values else 0


def read_final_comparison_speedups() -> dict[int, float]:
    speedups = {}

    if not FINAL_COMPARISON_TXT.exists():
        return speedups

    text = FINAL_COMPARISON_TXT.read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        match = re.search(r"Pitanje\s+(\d+).*?(\d+(?:\.\d+)?)x", line)
        if match:
            speedups[int(match.group(1))] = float(match.group(2))

    return speedups


def get_database_counts() -> dict[str, int]:
    db = MongoClient("mongodb://localhost:27017")[DB_NAME]

    return {
        "ml_movies": db.ml_movies.count_documents({}),
        "ml_ratings": db.ml_ratings.count_documents({}),
        "ml_tags": db.ml_tags.count_documents({}),
        "ml_genome_scores": db.ml_genome_scores.count_documents({}),
        "tmdb_movies_metadata": db.tmdb_movies_metadata.count_documents({}),
        "tmdb_credits": db.tmdb_credits.count_documents({}),
        "tmdb_keywords": db.tmdb_keywords.count_documents({}),
        "movies_optimized": db.movies_optimized.count_documents({}),
        "user_profiles_optimized": db.user_profiles_optimized.count_documents({}),
    }


def get_v2_coverage_counts() -> dict[str, int]:
    db = MongoClient("mongodb://localhost:27017")[DB_NAME]

    return {
        "Svi v2 filmovi": db.movies_optimized.count_documents({}),
        "Sa TMDB id": db.movies_optimized.count_documents({"tmdbId": {"$ne": None}}),
        "Sa TMDB naslovom": db.movies_optimized.count_documents({"tmdbTitle": {"$ne": None}}),
        "Sa budžetom": db.movies_optimized.count_documents({"commercial.budget": {"$gt": 0}}),
        "Sa prihodom": db.movies_optimized.count_documents({"commercial.revenue": {"$gt": 0}}),
        "Sa glumcima": db.movies_optimized.count_documents({"people.castCount": {"$gt": 0}}),
        "Sa režiserima": db.movies_optimized.count_documents({"people.directors.0": {"$exists": True}}),
        "Sa genome tagovima": db.movies_optimized.count_documents({"genome.highRelevanceTags.0": {"$exists": True}}),
    }


def create_document_count_chart() -> None:
    counts = get_database_counts()

    labels = list(counts.keys())
    values = list(counts.values())

    plt.figure(figsize=(12, 7))
    bars = plt.barh(labels, values)

    plt.xscale("log")
    plt.title("Broj dokumenata po kolekcijama")
    plt.xlabel("Broj dokumenata - log skala")
    plt.ylabel("Kolekcija")

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" {value:,}".replace(",", "."),
            va="center",
            fontsize=9,
        )

    save_chart("broj_dokumenata.png")


def create_execution_time_chart(v1: dict[int, dict[str, float]], v2: dict[int, dict[str, float]]) -> None:
    questions = sorted(v1.keys())
    x = range(len(questions))

    v1_times = [v1[q]["time"] for q in questions]
    v2_times = [v2[q]["time"] for q in questions]

    width = 0.35

    plt.figure(figsize=(11, 6))
    plt.bar([i - width / 2 for i in x], v1_times, width=width, label="V1 - sirova šema")
    plt.bar([i + width / 2 for i in x], v2_times, width=width, label="V2 - optimizovana šema")

    plt.yscale("log")
    plt.title("Vrijeme izvršavanja upita: V1 vs V2")
    plt.xlabel("Analitičko pitanje")
    plt.ylabel("Vrijeme izvršavanja u sekundama - log skala")
    plt.xticks(list(x), [f"Pitanje {q}" for q in questions])
    plt.legend()

    for i, value in enumerate(v1_times):
        plt.text(i - width / 2, value, f"{value:.3f}s", ha="center", va="bottom", fontsize=8)

    for i, value in enumerate(v2_times):
        plt.text(i + width / 2, value, f"{value:.3f}s", ha="center", va="bottom", fontsize=8)

    save_chart("vrijeme_izvrsavanja.png")


def create_speedup_chart(speedups: dict[int, float]) -> None:
    questions = sorted(speedups.keys())
    values = [speedups[q] for q in questions]

    plt.figure(figsize=(11, 6))
    bars = plt.bar([f"Pitanje {q}" for q in questions], values)

    plt.title("Ubrzanje v2 šeme u odnosu na v1")
    plt.xlabel("Analitičko pitanje")
    plt.ylabel("Ubrzanje")

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.2f}x",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    save_chart("ubrzanje_po_upitu.png")





def create_v2_coverage_chart() -> None:
    counts = get_v2_coverage_counts()

    labels = list(counts.keys())
    values = list(counts.values())

    plt.figure(figsize=(12, 7))
    bars = plt.barh(labels, values)

    plt.title("Pokrivenost podataka u kolekciji movies_optimized")
    plt.xlabel("Broj filmova")
    plt.ylabel("Tip dostupnih podataka")

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" {value:,}".replace(",", "."),
            va="center",
            fontsize=9,
        )

    save_chart("v2_pokrivenost_podataka.png")


def main() -> None:
    v1 = read_summary_csv(V1_SUMMARY_CSV)
    v2 = read_summary_csv(V2_SUMMARY_CSV)
    speedups = read_final_comparison_speedups()

    create_document_count_chart()
    create_execution_time_chart(v1, v2)
    create_speedup_chart(speedups)
    create_result_count_chart(v1, v2)
    create_v2_coverage_chart()

    print("")
    print("Grafici su uspješno generisani.")
    print(f"Folder: {CHARTS_DIR}")


if __name__ == "__main__":
    main()