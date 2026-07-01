import csv
from pathlib import Path


V1_CSV = Path("v1/results/v1_summary.csv")
V2_CSV = Path("v2/results/v2_summary.csv")

OUTPUT_TXT = Path("results/final_comparison.txt")
OUTPUT_CSV = Path("results/final_comparison.csv")


def read_summary(path, time_column):
    rows = {}

    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            question = int(row["question"])
            rows[question] = {
                "time": float(row[time_column]),
                "count": int(row["result_count"]),
            }

    return rows


def main():
    v1_rows = read_summary(V1_CSV, "v1_time_seconds")
    v2_rows = read_summary(V2_CSV, "v2_time_seconds")

    question_texts = {
        1: "Science Fiction filmovi poslije 2000. godine sa ocjenom > 4.0, najmanje 5.000 ocjena, budzetom > 50 miliona i najmanje 3 glumca.",
        2: "Glumci iz prva 3 mjesta u cast listi u filmovima sa ocjenom > 4.0, najmanje 1.000 ocjena i prihodom vecim od budzeta.",
        3: "Filmovi sa ocjenom > 4.1, najmanje 2.000 ocjena, popularnoscu < 15 i budzetom vecim od prihoda.",
        4: "Reziseri sa najmanje 3 filma, ocjenom > 4.0, najmanje 1.000 ocjena i konkretnim genome tagovima relevantnosti > 0.7.",
        5: "Preporuka filmova za userId = 123 na osnovu visokih ocjena, zajednickih zanrova, glumaca i rezisera.",
    }

    lines = []
    csv_lines = [
        "question,description,v1_time_seconds,v2_time_seconds,result_count,speedup"
    ]

    lines.append("FINALNO POREĐENJE V1 I V2 ŠEME")
    lines.append("=" * 90)
    lines.append("Pitanje | V1 vrijeme | V2 vrijeme | Broj rezultata | Ubrzanje")
    lines.append("-" * 90)

    for question in range(1, 6):
        v1_time = v1_rows[question]["time"]
        v2_time = v2_rows[question]["time"]
        result_count = v2_rows[question]["count"]

        speedup = v1_time / v2_time if v2_time > 0 else 0

        lines.append(
            f"Pitanje {question} | {v1_time:.3f}s | {v2_time:.3f}s | "
            f"{result_count} | {speedup:.2f}x brze"
        )

        csv_lines.append(
            f'{question},"{question_texts[question]}",{v1_time:.3f},{v2_time:.3f},{result_count},{speedup:.2f}'
        )

    lines.append("")
    lines.append("Zakljucak:")
    lines.append(
        "Optimizovana v2 sema znacajno ubrzava izvrsavanje slozenih analitickih upita. "
        "U v1 semi podaci su rasporedjeni kroz vise kolekcija i zahtijevaju grupisanje, povezivanje i filtriranje nad velikim brojem dokumenata. "
        "U v2 semi su najvazniji podaci unaprijed spojeni u kolekciji movies_optimized, a profil korisnika je pripremljen u user_profiles_optimized."
    )

    output_text = "\n".join(lines)

    print(output_text)

    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TXT.write_text(output_text, encoding="utf-8")
    OUTPUT_CSV.write_text("\n".join(csv_lines), encoding="utf-8")

    print("")
    print(f"TXT sacuvan u: {OUTPUT_TXT}")
    print(f"CSV sacuvan u: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()