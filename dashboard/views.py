import json
import pandas as pd
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import DatasetStatus
from .services import COUNTRIES, FEATURES, INDICATORS, fit_model, panel_csv, panel_frame, refresh_dataset

def home(request):
    return render(request, "index.html")

def _json_records(frame):
    clean = frame.astype(object).where(pd.notna(frame), None)
    return json.loads(clean.to_json(orient="records"))

def _summary(frame):
    required = ["temp_c", "rainfall_mm", "yield_kg_ha", "ag_land_pct"]
    has_rows = not frame.empty
    valid = frame.dropna(subset=required) if not frame.empty else frame
    return {
        "region": "Eurasia",
        "countries": int(valid.iso3.nunique()) if not valid.empty else (0 if has_rows else None),
        "years": int(valid.year.nunique()) if not valid.empty else (0 if has_rows else None),
        "year_start": int(valid.year.min()) if not valid.empty else None,
        "year_end": int(valid.year.max()) if not valid.empty else None,
        "observations": int(len(valid)) if has_rows else None,
        "mean_temp_c": round(float(valid.temp_c.mean()), 2) if not valid.empty else None,
        "mean_annual_precip_mm": round(float(valid.rainfall_mm.mean()), 1) if not valid.empty else None,
        "mean_yield_kg_ha": round(float(valid.yield_kg_ha.mean()), 1) if not valid.empty else None,
        "mean_ag_land_pct": round(float(valid.ag_land_pct.mean()), 2) if not valid.empty else None,
        "missing": {column: int(frame[column].isna().sum()) for column in required + ["humidity_pct"]} if has_rows else {column: None for column in required + ["humidity_pct"]},
        "available": not valid.empty,
        "message": None if not valid.empty else "No complete country-year observations are loaded. Use Refresh data to retrieve the source datasets.",
    }

def api_data(request):
    frame = panel_frame()
    country = request.GET.get("country", "ALL")
    if country != "ALL":
        frame = frame[frame.iso3 == country]
    status = DatasetStatus.objects.first()
    summary = _summary(frame)
    errors = json.loads(status.source_errors) if status and status.source_errors else []
    return JsonResponse({"rows": _json_records(frame), "summary": summary, "metadata": {"updated": status.updated_at.isoformat() if status else None, "rows": status.row_count if status else 0, "source_errors": errors}, "sources": INDICATORS})

def metadata(request):
    status = DatasetStatus.objects.first()
    frame = panel_frame()
    valid = frame.dropna(subset=["temp_c", "rainfall_mm", "yield_kg_ha", "ag_land_pct"]) if not frame.empty else frame
    available = valid.groupby("iso3").country.first().to_dict() if not valid.empty else {}
    return JsonResponse({"region": "Eurasia", "countries": [{"iso3": code, "name": name} for code, name in available.items()], "sources": INDICATORS, "updated": status.updated_at.isoformat() if status else None, "summary": _summary(frame), "source_errors": json.loads(status.source_errors) if status and status.source_errors else [], "coverage": "1981 onward; country-level NASA POWER representative-point climate estimates joined to World Bank country-year agriculture indicators."})

@csrf_exempt
def predict(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        body = json.loads(request.body or b"{}")
        code = body.get("country", "IND")
        frame = panel_frame()
        subset = frame[frame.iso3 == code].dropna(subset=["yield_kg_ha"])
        fitted = fit_model(frame)
        if fitted is None or subset.empty:
            return JsonResponse({"error": "Not enough country-year observations to fit a model. Refresh the dataset and try again."}, status=422)
        model, metrics = fitted
        latest = subset.sort_values("year").iloc[-1]
        baseline = {key: float(latest[key]) if pd.notna(latest[key]) else float(frame[key].median()) for key in FEATURES if key != "year"}
        baseline["year"] = int(latest.year)
        scenario = baseline.copy()
        scenario["temp_c"] += float(body.get("temp_delta", 1.5))
        rain_delta = float(body.get("rain_delta_pct", -10))
        scenario["rainfall_mm"] *= 1 + rain_delta / 100
        p0 = float(model.predict(pd.DataFrame([baseline]))[0])
        p1 = float(model.predict(pd.DataFrame([scenario]))[0])
        explanations = []
        for feature in FEATURES:
            altered = baseline.copy()
            step = float(frame[feature].std()) if frame[feature].notna().sum() > 1 else 0
            altered[feature] += step
            explanations.append({"feature": feature, "delta_yield": round(float(model.predict(pd.DataFrame([altered]))[0] - p0), 1), "step": round(step, 2)})
        return JsonResponse({"country": latest.country, "year": int(latest.year), "baseline": round(p0, 1), "scenario": round(p1, 1), "change": round(p1-p0, 1), "change_pct": round(100*(p1-p0)/p0, 2) if p0 else None, "metrics": metrics, "explanations": explanations, "scenario_inputs": {"temperature_delta_c": scenario["temp_c"]-baseline["temp_c"], "rainfall_delta_pct": rain_delta}})
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"error": f"Invalid scenario: {exc}"}, status=400)

@csrf_exempt
def refresh(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        count = refresh_dataset()
    except Exception as exc:
        return JsonResponse({"error": f"Data refresh failed: {exc}"}, status=502)
    if not count:
        status = DatasetStatus.objects.first()
        errors = json.loads(status.source_errors) if status and status.source_errors else []
        return JsonResponse({"error": "No observations were returned. Check network access and upstream source responses.", "source_errors": errors}, status=502)
    status = DatasetStatus.objects.first()
    return JsonResponse({"rows": count, "valid_observations": status.valid_observations, "countries": status.countries_count, "year_start": status.year_start, "year_end": status.year_end, "missing": json.loads(status.missing_data), "source_errors": json.loads(status.source_errors), "updated": timezone.now().isoformat()})

def download(request):
    frame = panel_frame()
    if frame.empty:
        return JsonResponse({"error": "Dataset unavailable; refresh the dataset first."}, status=503)
    response = HttpResponse(panel_csv(frame), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="eurasia_climate_agriculture_panel.csv"'
    return response
