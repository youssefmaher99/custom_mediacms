from django.db import migrations, models
import django.db.models.deletion
import files.models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0005_new_favorite_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='Media',
            name='favorites',
             field=models.ManyToManyField(
                to='users.User',
                related_name='favorite_medias',
                blank=True,
            ),
        ),
    ]