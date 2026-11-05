#!/usr/bin/env python3
"""Download the five Kaggle datasets used by the charts into data_prep/raw/.

    python3 fetch_datasets.py            # Kaggle API if configured, otherwise public GitHub mirrors
    python3 fetch_datasets.py --kaggle   # require the Kaggle API (needs ~/.kaggle/kaggle.json)

Copies are already included in raw/, so you only need this to re-download or to prove provenance.

| file               | chart    | Kaggle dataset (original)                                                   | rows |
|--------------------|----------|-----------------------------------------------------------------------------|------|
| vgsales.csv        | pie      | https://www.kaggle.com/datasets/gregorut/videogamesales                     | 16598|
| diamonds.csv       | bar      | https://www.kaggle.com/datasets/shivam2503/diamonds                         | 53940|
| penguins.csv       | scatter  | https://www.kaggle.com/datasets/parulpandey/palmer-archipelago-antarctica-penguin-data | 344 |
| gapminder.csv      | line     | https://www.kaggle.com/datasets/tklimonova/gapminder-datacamp-2007 (Gapminder World 1952-2007) | 1704 |
| air_passengers.csv | heatmap  | https://www.kaggle.com/datasets/rakannimer/air-passengers                   | 144  |

Mirrors hold the same records with small format differences that prepare_charts.py accepts:
penguins (bill_* vs Kaggle's culmen_*), diamonds (Kaggle adds an index column), air passengers
(Kaggle: Month "1949-01", #Passengers; mirror: year, month name, passengers), gapminder (column-name
spellings such as lifeExp / life_exp).
Standard library only.
"""
import argparse
import csv
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

DATASETS = {
    "vgsales.csv": {
        "kaggle": "gregorut/videogamesales", "kaggle_file": "vgsales.csv", "rows": 16598,
        "mirror": "https://raw.githubusercontent.com/ansegura7/DataViz_VideoGameSales/master/data/vgsales.csv",
        "columns": ["Rank", "Name", "Platform", "Year", "Genre", "Publisher", "Global_Sales"],
    },
    "diamonds.csv": {
        "kaggle": "shivam2503/diamonds", "kaggle_file": "diamonds.csv", "rows": 53940,
        "mirror": "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/diamonds.csv",
        "columns": ["clarity", "price"],
    },
    "penguins.csv": {
        "kaggle": "parulpandey/palmer-archipelago-antarctica-penguin-data", "kaggle_file": "penguins_size.csv", "rows": 344,
        "mirror": "https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv",
        "columns": ["species"],
    },
    "gapminder.csv": {
        "kaggle": "tklimonova/gapminder-datacamp-2007", "kaggle_file": None, "rows": 1704,
        "mirror": "https://raw.githubusercontent.com/plotly/datasets/master/gapminderDataFiveYear.csv",
        "columns": [],
    },
    "air_passengers.csv": {
        "kaggle": "rakannimer/air-passengers", "kaggle_file": "AirPassengers.csv", "rows": 144,
        "mirror": "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/flights.csv",
        "columns": [],
    },
}


def count_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r)
        return header, sum(1 for row in r if row)


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def via_kaggle(name, d):
    if not shutil.which("kaggle"):
        raise RuntimeError("kaggle CLI not installed (pip install kaggle)")
    tmp = os.path.join(RAW, "_kaggle_tmp")
    os.makedirs(tmp, exist_ok=True)
    subprocess.run(["kaggle", "datasets", "download", "-d", d["kaggle"], "-p", tmp, "--unzip", "--force"], check=True)
    for z in glob.glob(os.path.join(tmp, "*.zip")):
        zipfile.ZipFile(z).extractall(tmp)
    csvs = sorted(glob.glob(os.path.join(tmp, "**", "*.csv"), recursive=True))
    src = os.path.join(tmp, d["kaggle_file"]) if d["kaggle_file"] else (csvs[0] if len(csvs) == 1 else "")
    if not os.path.exists(src):
        raise RuntimeError(f"{d['kaggle_file']} not in Kaggle download: {os.listdir(tmp)}")
    shutil.copy(src, os.path.join(RAW, name))
    shutil.rmtree(tmp, ignore_errors=True)


def via_mirror(name, d):
    urllib.request.urlretrieve(d["mirror"], os.path.join(RAW, name))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kaggle", action="store_true", help="only use the Kaggle API")
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    for name, d in DATASETS.items():
        try:
            via_kaggle(name, d)
            how = "Kaggle API"
        except Exception as e:  # noqa: BLE001
            if a.kaggle:
                sys.exit(f"{name}: Kaggle download failed: {e}")
            via_mirror(name, d)
            how = f"mirror ({e})" if "kaggle CLI" not in str(e) else "GitHub mirror"
        header, n = count_rows(os.path.join(RAW, name))
        missing = [c for c in d["columns"] if c not in header and name != "penguins.csv"]
        ok = n == d["rows"] and not missing
        print(f"{'OK ' if ok else 'CHECK'} {name:20} {n:6} rows (expected {d['rows']})  via {how}  sha256 {sha256(os.path.join(RAW, name))[:16]}")


if __name__ == "__main__":
    main()
