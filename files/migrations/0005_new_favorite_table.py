from django.db import migrations, models
import django.db.models.deletion
import files.models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0004_add_cover_image_and_category_to_playlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='Playlist',
            name='favorites',
             field=models.ManyToManyField(
                to='users.User',
                related_name='favorite_shows',
                blank=True,
            ),
        ),
    ]