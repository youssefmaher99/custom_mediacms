from django.db import migrations, models
import files.models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0007_search_playlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='Playlist',
            name='thumbnail_image',
            field=models.FileField(
                "thumbnail image",
                upload_to=files.models.thumbnail_playlist_file_path,
                max_length=500,
                help_text="thumbnail image",
                null=True
            ),
        ),
    ]

