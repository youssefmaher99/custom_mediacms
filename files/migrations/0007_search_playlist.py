from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.search
from django.contrib.postgres.indexes import GinIndex
import files.models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0006_favorite_media_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='Playlist',
            name='search',
             field=django.contrib.postgres.search.SearchVectorField(
                        help_text="used to store all searchable info and metadata for a Media",
                        null=True,
                ),
        ),
        migrations.AddIndex(
            model_name="Playlist",
            index=django.contrib.postgres.indexes.GinIndex(fields=["search"], name="files_playlist_search_gin"),
        ),
    ]


