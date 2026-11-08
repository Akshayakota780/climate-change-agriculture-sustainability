from django.db import models

class Observation(models.Model):
    """Joined annual country-level climate and agriculture record."""
    country = models.CharField(max_length=100)
    iso3 = models.CharField(max_length=3, db_index=True)
    year = models.PositiveSmallIntegerField(db_index=True)
    temp_c = models.FloatField(null=True, blank=True)
    rainfall_mm = models.FloatField(null=True, blank=True)
    humidity_pct = models.FloatField(null=True, blank=True)
    soil_moisture = models.FloatField(null=True, blank=True)
    ag_land_pct = models.FloatField(null=True, blank=True)
    yield_kg_ha = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["iso3", "year"]
        constraints = [models.UniqueConstraint(fields=["iso3", "year"], name="unique_country_year_observation")]

    def __str__(self):
        return f"{self.country} · {self.year}"

class DatasetStatus(models.Model):
    """Single-row metadata for the most recently loaded source panel."""
    updated_at = models.DateTimeField(auto_now=True)
    row_count = models.PositiveIntegerField(default=0)
    valid_observations = models.PositiveIntegerField(default=0)
    countries_count = models.PositiveSmallIntegerField(default=0)
    year_start = models.PositiveSmallIntegerField(null=True, blank=True)
    year_end = models.PositiveSmallIntegerField(null=True, blank=True)
    missing_data = models.TextField(default="{}")
    source_errors = models.TextField(default="[]")
