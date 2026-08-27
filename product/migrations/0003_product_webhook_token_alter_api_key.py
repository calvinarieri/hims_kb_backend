# Migration to add webhook_token and alter api_key on Product

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0002_product_github_url_productversion_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='webhook_token',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='api_key',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]

