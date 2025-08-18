from django.db import migrations, models
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def fix_waste_calculation_data(apps, schema_editor):
    """Fix waste calculation for existing products"""
    Product = apps.get_model('products', 'Product')
    
    WASTE_COEFFICIENTS = {
        'excellente': Decimal('0.82'),
        'bonne': Decimal('0.835'),
        'moyenne': Decimal('0.85'),
        'mauvaise': Decimal('0.875'),
    }
    
    updated_count = 0
    
    for product in Product.objects.all():
        original_waste_vendus = product.waste_vendus_kg
        original_waste_price = product.waste_vendus_price
        
        # Fix None values - set to 0 if None
        if product.waste_vendus_kg is None:
            product.waste_vendus_kg = Decimal('0')
            
        if product.waste_vendus_price is None:
            product.waste_vendus_price = Decimal('0')
        
        # Recalculate total waste if needed
        waste_coefficient = WASTE_COEFFICIENTS.get(product.quality, Decimal('0.85'))
        correct_total_waste = Decimal(str(product.quantity)) * waste_coefficient
        
        if product.total_waste_kg != correct_total_waste:
            product.total_waste_kg = correct_total_waste
            logger.info(f"Updated total waste for product {product.id}: {correct_total_waste}kg")
        
        # Recalculate non-vendus waste
        waste_vendus = product.waste_vendus_kg if product.waste_vendus_kg is not None else Decimal('0')
        product.waste_non_vendus_kg = product.total_waste_kg - waste_vendus
        
        # Save if anything changed
        if (original_waste_vendus != product.waste_vendus_kg or 
            original_waste_price != product.waste_vendus_price or
            product.waste_non_vendus_kg is None):
            
            product.save()
            updated_count += 1
            logger.info(f"Fixed product {product.id} waste calculation")
    
    logger.info(f"Updated {updated_count} products with corrected waste calculations")


def reverse_fix_waste_calculation_data(apps, schema_editor):
    """Reverse the migration (optional - you might not want to do this)"""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('products', '0002_initial'),
    ]

    operations = [
        # First, allow null values for waste fields
        migrations.AlterField(
            model_name='product',
            name='waste_vendus_kg',
            field=models.DecimalField(
                blank=True, 
                decimal_places=3, 
                help_text='Sold waste in kg', 
                max_digits=10, 
                null=True
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='waste_vendus_price',
            field=models.DecimalField(
                blank=True, 
                decimal_places=2, 
                help_text='Revenue from sold waste in DT', 
                max_digits=10, 
                null=True
            ),
        ),
        # Then run the data fix
        migrations.RunPython(
            fix_waste_calculation_data, 
            reverse_fix_waste_calculation_data
        ),
    ]