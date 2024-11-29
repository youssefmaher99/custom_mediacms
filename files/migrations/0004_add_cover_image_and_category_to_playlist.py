from django.db import migrations, models
import django.db.models.deletion
import files.models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0003_auto_20210927_1245'),
    ]

    operations = [
        migrations.AddField(
            model_name='Playlist',
            name='cover_image',
            field=models.FileField(
                "cover image",
                upload_to=files.models.cover_image_file_path,
                max_length=500,
                help_text="cover image",
                null=True
            ),
        ),
        migrations.AddField(
            model_name="playlist",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.SET_NULL,
                related_name="playlists",
                to="files.Category",
                to_field="title"
            ),
        ),
    ]