from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


REACTION_COLUMNS = ["primary_reaction", "secondary_reaction", "tertiary_reaction"]
NUMERIC_NAN_KEEP = {"weight", "dose", "therapy_duration_days", "patient_weight_kg"}
CLEAN_SUFFIXES = {
    "hcl",
    "tablet",
    "tablets",
    "injection",
    "inj",
    "capsule",
    "capsules",
    "solution",
    "suspension",
    "cream",
    "gel",
    "ointment",
    "syrup",
}


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: re.sub(r"\s+", "_", col.strip().lower()) for col in df.columns}
    return df.rename(columns=renamed)


def _normalize_reported_drug(value: object) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    # Remove punctuation and collapse whitespace so token-based suffix cleanup is reliable.
    text = re.sub(r"[^a-z0-9\s/+.-]", " ", text)
    tokens = text.split()

    while tokens and tokens[-1] in CLEAN_SUFFIXES:
        tokens.pop()

    cleaned = " ".join(tokens).strip()
    return cleaned or None


def normalize_drug(df: pd.DataFrame) -> pd.DataFrame:
    generic = (
        df["drug_name_generic"].astype("string").str.strip().str.lower()
        if "drug_name_generic" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )

    reported = (
        df["drug_name_reported"].map(_normalize_reported_drug)
        if "drug_name_reported" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )

    df["drug_clean"] = generic.where(generic.notna() & (generic != ""), reported)
    return df


def normalize_reactions(df: pd.DataFrame) -> pd.DataFrame:
    available = [col for col in REACTION_COLUMNS if col in df.columns]
    if not available:
        raise ValueError(
            "No reaction columns found. Expected one or more of: "
            f"{', '.join(REACTION_COLUMNS)}"
        )

    id_columns = [c for c in df.columns if c not in available]
    melted = df.melt(
        id_vars=id_columns,
        value_vars=available,
        var_name="reaction_source",
        value_name="reaction",
    )
    melted["reaction"] = melted["reaction"].astype("string").str.strip().str.lower()
    melted = melted.loc[melted["reaction"].notna() & (melted["reaction"] != "")].copy()
    return melted


def engineer_dates(df: pd.DataFrame) -> pd.DataFrame:
    if "receive_date" not in df.columns:
        return df

    df["receive_date"] = pd.to_datetime(df["receive_date"], errors="coerce")
    df["report_year"] = df["receive_date"].dt.year
    df["report_month"] = df["receive_date"].dt.month
    df["report_quarter"] = df["receive_date"].dt.to_period("Q").astype("string")
    return df


def apply_missing_value_strategy(df: pd.DataFrame) -> pd.DataFrame:
    if "patient_age_years" in df.columns and "patient_age_group" in df.columns:
        grouped_median = df.groupby("patient_age_group")["patient_age_years"].transform("median")
        df["patient_age_years"] = df["patient_age_years"].fillna(grouped_median)
        remaining_median = df["patient_age_years"].median()
        df["patient_age_years"] = df["patient_age_years"].fillna(remaining_median)

    if "time_to_onset_days" in df.columns:
        global_median = df["time_to_onset_days"].median()
        df["time_to_onset_days"] = df["time_to_onset_days"].fillna(global_median)

    protected_columns = set(NUMERIC_NAN_KEEP)
    categorical_cols = [
        col
        for col in df.columns
        if col not in protected_columns and pd.api.types.is_object_dtype(df[col])
    ]

    for col in categorical_cols:
        df[col] = df[col].fillna("Unknown")

    return df


def add_duplicate_key(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["patient_age_years", "drug_clean", "reaction", "reporter_country"]:
        if col not in df.columns:
            df[col] = pd.NA

    key_df = pd.DataFrame(
        {
            "patient_age_years": df["patient_age_years"].astype("string"),
            "drug_clean": df["drug_clean"].astype("string"),
            "reaction": df["reaction"].astype("string"),
            "reporter_country": df["reporter_country"].astype("string"),
        }
    )
    df["dup_key"] = pd.util.hash_pandas_object(key_df, index=False).astype("uint64")
    return df


def memory_usage_mb(df: pd.DataFrame) -> float:
    return df.memory_usage(deep=True).sum() / (1024**2)


def optimize_memory(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        dtype = df[col].dtype

        if pd.api.types.is_object_dtype(dtype):
            df[col] = df[col].astype("category")
        elif pd.api.types.is_float_dtype(dtype):
            df[col] = pd.to_numeric(df[col], downcast="float")
        elif pd.api.types.is_integer_dtype(dtype):
            df[col] = pd.to_numeric(df[col], downcast="integer")

    return df


def _load_input(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file type '{suffix}'. Use .xlsx, .xls, or .csv")


def _output_paths(input_path: Path) -> tuple[Path, Path]:
    out_dir = input_path.parent
    parquet_path = out_dir / "clean_faers.parquet"
    csv_path = out_dir / "clean_faers.csv"
    return parquet_path, csv_path


def _fallback_output_path(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{ts}{path.suffix}")


def run_pipeline(input_excel_path: str) -> pd.DataFrame:
    input_path = Path(input_excel_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = _load_input(input_path)
    df = standardize_columns(df)

    df = normalize_drug(df)
    df = normalize_reactions(df)
    df = engineer_dates(df)
    df = apply_missing_value_strategy(df)
    df = add_duplicate_key(df)

    before_mb = memory_usage_mb(df)
    df = optimize_memory(df)

    after_mb = memory_usage_mb(df)
    print(f"Memory usage before optimization: {before_mb:.2f} MB")
    print(f"Memory usage after optimization:  {after_mb:.2f} MB")
    if before_mb > 0:
        reduction = ((before_mb - after_mb) / before_mb) * 100
        print(f"Memory reduced by: {reduction:.2f}%")

    parquet_path, csv_path = _output_paths(input_path)

    try:
        df.to_parquet(parquet_path, index=False)
    except PermissionError:
        parquet_path = _fallback_output_path(parquet_path)
        df.to_parquet(parquet_path, index=False)
        print("Parquet target was locked; wrote fallback file instead.")

    try:
        df.to_csv(csv_path, index=False)
    except PermissionError:
        csv_path = _fallback_output_path(csv_path)
        df.to_csv(csv_path, index=False)
        print("CSV target was locked; wrote fallback file instead.")

    print(f"Saved Parquet: {parquet_path}")
    print(f"Saved CSV:     {csv_path}")

    return df


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FAERS cleaning pipeline")
    parser.add_argument(
        "input_path",
        type=str,
        help="Path to input FAERS Excel (.xlsx/.xls) or CSV file",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    run_pipeline(args.input_path)


if __name__ == "__main__":
    main()
