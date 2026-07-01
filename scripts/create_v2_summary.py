import re
from pathlib import Path


RESULTS_DIR = Path("v2/results")
OUTPUT_TXT = RESULTS_DIR / "v2_summary.txt"
OUTPUT_CSV = RESULTS_DIR / "v2_summary.csv"


def extract_value(pattern, text, default=""):
    match = re.search(pattern, text)

    if not match:
        return default

    return match.group(1)


def main():
    rows = []

    for question_number in range(1, 6):
        file_path = RESULTS_DIR / f"question_{question_number}_v2_results.txt"

        if not file_path.exists():
            rows.append({
                "question": question_number,
                "time": "NEDOSTAJE",
                "count": "NEDOSTAJE",
                "file": str(file_path),
            })
            continue

        text = file_path.read_text(encoding="utf-8")

        execution_time = extract_value(
            r"Vrijeme izvrsavanja:\s*([0-9.]+)\s*sekundi",
            text,
            "NIJE PRONADJENO"
        )

        result_count = extract_value(
            r"Broj rezultata:\s*([0-9]+)",
            text,
            "NIJE PRONADJENO"
        )

        rows.append({
            "question": question_number,
            "time": execution_time,
            "count": result_count,
            "file": str(file_path),
        })

    lines = []
    lines.append("V2 SUMMARY - OPTIMIZOVANA SEMA")
    lines.append("=" * 60)
    lines.append("Pitanje | Vrijeme izvrsavanja | Broj rezultata")
    lines.append("-" * 60)

    for row in rows:
        lines.append(
            f"Pitanje {row['question']} | {row['time']} sekundi | {row['count']} rezultata"
        )

    summary_text = "\n".join(lines)

    print(summary_text)

    OUTPUT_TXT.write_text(summary_text, encoding="utf-8")

    csv_lines = ["question,v2_time_seconds,result_count,file"]

    for row in rows:
        csv_lines.append(
            f"{row['question']},{row['time']},{row['count']},{row['file']}"
        )

    OUTPUT_CSV.write_text("\n".join(csv_lines), encoding="utf-8")

    print("")
    print(f"TXT sacuvan u: {OUTPUT_TXT}")
    print(f"CSV sacuvan u: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()