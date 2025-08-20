from django.db import migrations, models
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def apply_automatic_waste_calculation(apps, schema_editor):
    """Apply automatic waste calculation to all existing products"""
    Product = apps.get_model('products', 'Product')
    
    # Define the calculation rules (same as in model)
    WASTE_COEFFICIENTS = {
        'excellente': Decimal('0.82'),
        'bonne': Decimal('0.835'),
        'moyenne': Decimal('0.85'),
        'mauvaise': Decimal('0.875'),
    }
    
    WASTE_SOLD_PERCENTAGE = {
        'excellente': Decimal('0.75'),  
        'bonne': Decimal('0.65'),       
        'moyenne': Decimal('0.50'),   
        'mauvaise': Decimal('0.30'),   
    }
    
    WASTE_PRICE_PER_KG = {
        'excellente': Decimal('5.50'),  
        'bonne': Decimal('4.80'),       
        'moyenne': Decimal('4.00'),     
        'mauvaise': Decimal('3.20'),    
    }
    
    updated_count = 0
    
    for product in Product.objects.all():
        logger.info(f"Applying automatic waste calculation to product {product.id}")
        
        # Calculate total waste
        waste_coefficient = WASTE_COEFFICIENTS.get(product.quality, Decimal('0.85'))
        total_waste = Decimal(str(product.quantity)) * waste_coefficient
        
        # Calculate waste vendus automatically
        sold_percentage = WASTE_SOLD_PERCENTAGE.get(product.quality, Decimal('0.50'))
        waste_vendus = total_waste * sold_percentage
        
        # Calculate waste vendus price automatically
        price_per_kg = WASTE_PRICE_PER_KG.get(product.quality, Decimal('4.00'))
        waste_vendus_price = waste_vendus * price_per_kg
        
        # Calculate waste non vendus
        waste_non_vendus = total_waste - waste_vendus
        
        # Update the product
        product.total_waste_kg = total_waste
        product.waste_vendus_kg = waste_vendus
        product.waste_vendus_price = waste_vendus_price
        product.waste_non_vendus_kg = waste_non_vendus
        
        product.save()
        updated_count += 1
        
        logger.info(
            f"Product {product.id} updated - "
            f"Total waste: {total_waste}kg, "
            f"Vendus: {waste_vendus}kg ({float(sold_percentage * 100)}%), "
            f"Price: {waste_vendus_price}DT, "
            f"Non vendus: {waste_non_vendus}kg"
        )
    
    logger.info(f"Applied automatic waste calculation to {updated_count} products")


def reverse_automatic_waste_calculation(apps, schema_editor):
    """Reverse the automatic calculation (set waste fields to 0)"""
    Product = apps.get_model('products', 'Product')
    
    for product in Product.objects.all():
        product.waste_vendus_kg = Decimal('0')
        product.waste_vendus_price = Decimal('0')
        product.waste_non_vendus_kg = product.total_waste_kg
        product.save()


class Migration(migrations.Migration):
    dependencies = [
        ('products', '0003_fix_waste_calculation'), 
    ]

    operations = [
        migrations.RunPython(
            apply_automatic_waste_calculation,
            reverse_automatic_waste_calculation
        ),
    ]