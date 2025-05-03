import django
from django.db import migrations, models
import files.models

class Migration(migrations.Migration):
    dependencies = [
        ('files', '0008_thumbnail_playlist_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserEvents',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visit_time', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, to='users.user', db_index=True)),
                ('media', models.ForeignKey(on_delete=models.CASCADE, to='files.Media', db_index=True)),
                ('category', models.CharField(max_length=255)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['user', 'visit_time'], name='user_visit_idx'),
                ],
            },
        ),
    ]