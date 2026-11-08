from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="DatasetStatus",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("updated_at", models.DateTimeField(auto_now=True)), ("row_count", models.PositiveIntegerField(default=0))],
        ),
        migrations.CreateModel(
            name="Observation",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("country", models.CharField(max_length=100)), ("iso3", models.CharField(db_index=True, max_length=3)), ("year", models.PositiveSmallIntegerField(db_index=True)), ("temp_c", models.FloatField(blank=True, null=True)), ("rainfall_mm", models.FloatField(blank=True, null=True)), ("humidity_pct", models.FloatField(blank=True, null=True)), ("soil_moisture", models.FloatField(blank=True, null=True)), ("ag_land_pct", models.FloatField(blank=True, null=True)), ("yield_kg_ha", models.FloatField(blank=True, null=True))],
            options={"ordering": ["iso3", "year"]},
        ),
        migrations.AddConstraint(model_name="observation", constraint=models.UniqueConstraint(fields=("iso3", "year"), name="unique_country_year_observation")),
    ]
