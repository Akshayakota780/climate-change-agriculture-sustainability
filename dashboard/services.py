"""Source retrieval and model helpers kept separate from Django request handlers."""
from __future__ import annotations

import io
import calendar
import json
import requests
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from django.db import transaction
from .models import DatasetStatus, Observation

COUNTRIES = {
    "IND": ("India", 20.5937, 78.9629), "CHN": ("China", 35.8617, 104.1954),
    "RUS": ("Russia", 61.5240, 105.3188), "KAZ": ("Kazakhstan", 48.0196, 66.9237),
    "PAK": ("Pakistan", 30.3753, 69.3451), "BGD": ("Bangladesh", 23.6850, 90.3563),
    "NPL": ("Nepal", 28.3949, 84.1240), "LKA": ("Sri Lanka", 7.8731, 80.7718),
    "AFG": ("Afghanistan", 33.9391, 67.7100), "IRN": ("Iran", 32.4279, 53.6880),
    "TUR": ("Türkiye", 38.9637, 35.2433), "MNG": ("Mongolia", 46.8625, 103.8467),
    "UZB": ("Uzbekistan", 41.3775, 64.5853), "TKM": ("Turkmenistan", 38.9697, 59.5563),
    "KGZ": ("Kyrgyzstan", 41.2044, 74.7661), "TJK": ("Tajikistan", 38.8610, 71.2761),
    "AZE": ("Azerbaijan", 40.1431, 47.5769), "ARM": ("Armenia", 40.0691, 45.0382),
    "GEO": ("Georgia", 42.3154, 43.3569), "UKR": ("Ukraine", 48.3794, 31.1656),
    "BLR": ("Belarus", 53.7098, 27.9534), "MDA": ("Moldova", 47.4116, 28.3699),
}
WB = "https://api.worldbank.org/v2/country/{}/indicator/{}?format=json&per_page=2000"
POWER = "https://power.larc.nasa.gov/api/temporal/monthly/point"
INDICATORS = {
    "ag_land_pct": ("AG.LND.AGRI.ZS", "Agricultural land (% of land area)", "%"),
    "yield_kg_ha": ("AG.YLD.CREL.KG", "Cereal yield", "kg/ha"),
    "rainfall_mm": ("PRECTOTCORR", "Annual precipitation (NASA POWER monthly point estimates aggregated by year)", "mm/year"),
    "temp_c": ("T2M", "Air temperature at 2 m (NASA POWER point estimate)", "°C"),
    "humidity_pct": ("RH2M", "Relative humidity at 2 m (NASA POWER point estimate)", "%"),
}
FEATURES = ["temp_c", "rainfall_mm", "humidity_pct", "ag_land_pct", "year"]

def get_json(url, params=None):
    response = requests.get(url, params=params, timeout=45, headers={"User-Agent": "EurasiaClimateAgricultureResearch/1.0"})
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code} {response.reason}: {response.text[:300]}", response=response)
    return response.json()

def fetch_wb(code, indicator):
    payload = get_json(WB.format(code, indicator))
    if not payload or len(payload) < 2 or payload[1] is None:
        return {}
    return {int(row["date"]): row["value"] for row in payload[1] if row.get("value") is not None}

def refresh_dataset():
    """Fetch source records, join by ISO3/year, and atomically replace the SQLite panel."""
    rows = []
    source_errors = []
    end_year = pd.Timestamp.utcnow().year - 1
    # Pull the WDI series in two paginated bulk calls rather than issuing two requests
    # for each country. Restrict the result to real country codes in our Eurasian roster.
    wdi_values = {}
    for code, indicator in (("land", "AG.LND.AGRI.ZS"), ("yield", "AG.YLD.CREL.KG")):
        try:
            payload = get_json("https://api.worldbank.org/v2/country/all/indicator/{}".format(indicator), {"format": "json", "date": f"1981:{end_year}", "per_page": 20000})
            records = payload[1] if payload and len(payload) > 1 and payload[1] else []
            if not records:
                raise ValueError("World Bank API returned no country-year records")
            wdi_values[code] = {(item.get("countryiso3code"), int(item["date"])): item.get("value") for item in records if item.get("countryiso3code") and item.get("date") and item.get("value") is not None}
        except Exception as exc:
            source_errors.append(f"World Bank {indicator}: {exc}")
            wdi_values[code] = {}
    for code, (name, lat, lon) in COUNTRIES.items():
        land = {year: value for (iso, year), value in wdi_values.get("land", {}).items() if iso == code}
        yields = {year: value for (iso, year), value in wdi_values.get("yield", {}).items() if iso == code}
        common_years = sorted(set(land) & set(yields))
        if not common_years:
            continue
        try:
            power = get_json(POWER, {"parameters": "T2M,PRECTOTCORR,RH2M", "community": "AG", "longitude": lon, "latitude": lat, "start": "1981", "end": str(end_year), "format": "JSON"})
            props = power.get("properties", {}).get("parameter", {})
            required_climate = ("T2M", "PRECTOTCORR")
            if not all(props.get(key) for key in required_climate):
                raise ValueError("NASA POWER response is missing required annual temperature or precipitation data")
            country_rows = []
            for year in common_years:
                month_values = {key: [] for key in required_climate + ("RH2M",)}
                month_weights = []
                for month in range(1, 13):
                    days = calendar.monthrange(year, month)[1]
                    month_key = f"{year}{month:02d}"
                    month_weights.append(days)
                    for key in month_values:
                        raw = props.get(key, {}).get(month_key)
                        value = None if raw is None or raw == -999 else float(raw)
                        month_values[key].append(value if value is not None and pd.notna(value) else None)
                def weighted_mean(values):
                    pairs = [(value, month_weights[i]) for i, value in enumerate(values) if value is not None]
                    return sum(value * days for value, days in pairs) / sum(days for _, days in pairs) if pairs else None
                temp_mean = weighted_mean(month_values["T2M"])
                humidity_mean = weighted_mean(month_values["RH2M"])
                precip_values = month_values["PRECTOTCORR"]
                annual_precip = sum(value * month_weights[i] for i, value in enumerate(precip_values) if value is not None) if any(value is not None for value in precip_values) else None
                country_rows.append(Observation(country=name, iso3=code, year=year,
                    temp_c=temp_mean, rainfall_mm=annual_precip,
                    humidity_pct=humidity_mean, soil_moisture=None,
                    ag_land_pct=land[year], yield_kg_ha=yields[year]))
            rows.extend(country_rows)
        except Exception as exc:
            source_errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:240]}")
            continue
    if not rows:
        status, _ = DatasetStatus.objects.get_or_create(pk=1)
        status.source_errors = json.dumps(source_errors)
        status.save()
        return 0
    panel = pd.DataFrame([{"iso3": row.iso3, "year": row.year, "temp_c": row.temp_c, "rainfall_mm": row.rainfall_mm, "yield_kg_ha": row.yield_kg_ha, "ag_land_pct": row.ag_land_pct} for row in rows])
    required = ["temp_c", "rainfall_mm", "yield_kg_ha", "ag_land_pct"]
    valid = panel.dropna(subset=required)
    missing = {column: int(panel[column].isna().sum()) for column in required + ["humidity_pct"]}
    # Keep the last good panel if an upstream outage prevented every country from loading.
    with transaction.atomic():
        Observation.objects.all().delete()
        Observation.objects.bulk_create(rows, batch_size=1000)
        DatasetStatus.objects.update_or_create(pk=1, defaults={
            "row_count": len(rows), "valid_observations": len(valid),
            "countries_count": int(valid.iso3.nunique()),
            "year_start": int(valid.year.min()) if not valid.empty else None,
            "year_end": int(valid.year.max()) if not valid.empty else None,
            "missing_data": json.dumps(missing), "source_errors": json.dumps(source_errors),
        })
    return len(rows)

def panel_frame():
    columns = ["country", "iso3", "year", "temp_c", "rainfall_mm", "humidity_pct", "soil_moisture", "ag_land_pct", "yield_kg_ha"]
    return pd.DataFrame.from_records(Observation.objects.values(*columns), columns=columns)

def fit_model(frame):
    data = frame.dropna(subset=["yield_kg_ha"]).sort_values("year")
    if len(data) < 20:
        return None
    cutoff = data.year.quantile(.8)
    train, test = data[data.year <= cutoff], data[data.year > cutoff]
    if train.empty or test.empty:
        count = max(1, len(data) // 5)
        train, test = data.iloc[:-count], data.iloc[-count:]
    model = make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(n_estimators=180, min_samples_leaf=3, random_state=42, n_jobs=-1))
    model.fit(train[FEATURES], train.yield_kg_ha)
    pred = model.predict(test[FEATURES])
    metrics = {"n_train": len(train), "n_test": len(test), "cutoff_year": int(cutoff), "mae": round(float(mean_absolute_error(test.yield_kg_ha, pred)), 1), "r2": round(float(r2_score(test.yield_kg_ha, pred)), 3) if len(test)>1 else None, "test_start": int(test.year.min()), "test_end": int(test.year.max())}
    return model, metrics

def panel_csv(frame):
    output = io.StringIO()
    frame.to_csv(output, index=False)
    return output.getvalue()
