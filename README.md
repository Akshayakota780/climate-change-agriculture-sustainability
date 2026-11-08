# Climate Change Impact Prediction on Agricultural Land Sustainability

**A Eurasian Case Study Using Interpretable Machine Learning**

Django web application for exploring annual climate and agricultural productivity across Eurasia. Django views expose the data and scenario APIs, SQLite stores the refreshed country-year panel, and scikit-learn fits a Random Forest yield model with temporal holdout metrics and local sensitivity explanations.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000. Click **Load / refresh data** to retrieve the source series. The source requests can take a few minutes. Data is joined on ISO3 country code and year and saved to the local SQLite database (`db.sqlite3`); CSV export downloads the current database panel. The country selector is populated from complete observations actually present in the database, not from the candidate roster.

## Data sources and units

| Measure | Provider / identifier | Unit and interpretation |
|---|---|---|
| 2 m air temperature | NASA POWER monthly API, `T2M` | Day-weighted °C annual mean |
| Precipitation | NASA POWER monthly API, `PRECTOTCORR` | Monthly mm/day multiplied by days per month and summed to mm/year |
| Relative humidity | NASA POWER monthly API, `RH2M` | Day-weighted annual mean % |
| Agricultural land | World Bank WDI, `AG.LND.AGRI.ZS` | Percent of land area |
| Cereal yield | World Bank WDI, `AG.YLD.CREL.KG` | kg per hectare |

NASA POWER docs: <https://power.larc.nasa.gov/docs/services/api/temporal/>. World Bank API: <https://api.worldbank.org/v2/>. Indicator pages: [agricultural land](https://data.worldbank.org/indicator/AG.LND.AGRI.ZS), [cereal yield](https://data.worldbank.org/indicator/AG.YLD.CREL.KG).

The country candidate roster covers India, China, Russia, Kazakhstan, Pakistan, Bangladesh, Nepal, Sri Lanka, Afghanistan, Iran, Türkiye, Mongolia, Uzbekistan, Turkmenistan, Kyrgyzstan, Tajikistan, Azerbaijan, Armenia, Georgia, Ukraine, Belarus, and Moldova. Only countries with valid source overlap are displayed. Climate is requested monthly from NASA POWER and aggregated to year: temperature and humidity use day-weighted means, while precipitation uses monthly mean daily precipitation multiplied by days per month and summed to annual millimeters. These are representative-coordinate point estimates, not national spatial averages. Missing observations remain missing in storage and charts; the dashboard reports missing counts. Model inputs are median-imputed only during training/inference.

Coverage metrics and missing-field counts are calculated from the stored panel and exposed at `/api/data` and `/api/metadata`. The refresh endpoint returns source errors when upstream requests fail; if no new rows are received, the last successfully loaded panel is retained.

The scenario model's yield estimates are exploratory sensitivities, not causal effects or forecasts. Evaluation holds out later years. Cereal yields also reflect technology, crop mix, irrigation, inputs, policy, and other factors beyond climate.
