from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("dashboard", "0001_initial")]
    operations = [
        migrations.AddField(model_name="datasetstatus", name="valid_observations", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="datasetstatus", name="countries_count", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="datasetstatus", name="year_start", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="datasetstatus", name="year_end", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="datasetstatus", name="missing_data", field=models.TextField(default="{}")),
        migrations.AddField(model_name="datasetstatus", name="source_errors", field=models.TextField(default="[]")),
    ]
