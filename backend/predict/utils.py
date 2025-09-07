import io
import base64
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_agg import FigureCanvasAgg
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, status
from products.models import Product
from .ml_service import global_prediction_service
import logging
import matplotlib
matplotlib.use('Agg')

logger = logging.getLogger(__name__)


def create_waste_partition_chart(fitoura_amount, margin_amount):
    """
    Create a pie chart showing the partition of waste (Fitoura vs Margin)
    """
    try:
        if fitoura_amount <= 0 and margin_amount <= 0:
            raise ValueError("No waste data available")

        data = [fitoura_amount, margin_amount]
        labels = ['Déchet Fitoura', 'Déchet Margin']
        colors = ['#FF6B6B', '#4ECDC4']

        plt.figure(figsize=(8, 6))
        fig, ax = plt.subplots(figsize=(8, 6))

        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors,
            explode=(0.05, 0.05)  # Slight separation for better visibility
        )

        ax.set_title('Répartition des Déchets',
                     fontsize=14, fontweight='bold', pad=20)

        # Style the text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(11)

        for text in texts:
            text.set_fontsize(10)
            text.set_fontweight('bold')

        # Add total waste info
        total_waste = fitoura_amount + margin_amount
        plt.figtext(0.5, 0.02, f'Total des Déchets: {total_waste:.2f} kg',
                    ha='center', fontsize=10, style='italic')

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64

    except Exception as e:
        logger.error(f"Error creating waste partition chart: {e}")
        return create_error_chart(f"Erreur Graphique Déchets:\n{str(e)}")


def create_cost_distribution_chart(costs_dict):
    """
    Create a pie chart showing the distribution of different costs
    """
    try:
        # Extract cost values
        electricity_cost = costs_dict.get('electricity_cost_tnd', 0)
        water_cost = costs_dict.get('water_cost_tnd', 0)
        labor_cost = costs_dict.get('labor_cost_tnd', 0)

        # Filter out zero costs
        cost_data = []
        cost_labels = []
        if electricity_cost > 0:
            cost_data.append(electricity_cost)
            cost_labels.append('Coût Électricité')
        if water_cost > 0:
            cost_data.append(water_cost)
            cost_labels.append('Coût Eau')
        if labor_cost > 0:
            cost_data.append(labor_cost)
            cost_labels.append('Coût Main d\'Œuvre')

        if not cost_data:
            raise ValueError("No cost data available")

        colors = ['#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']

        plt.figure(figsize=(8, 6))
        fig, ax = plt.subplots(figsize=(8, 6))

        wedges, texts, autotexts = ax.pie(
            cost_data,
            labels=cost_labels,
            autopct='%1.1f%%',
            startangle=45,
            colors=colors[:len(cost_data)],
            explode=[0.02] * len(cost_data)  # Small separation
        )

        ax.set_title('Répartition des Coûts Opérationnels',
                     fontsize=14, fontweight='bold', pad=20)

        # Style the text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(11)

        for text in texts:
            text.set_fontsize(10)
            text.set_fontweight('bold')

        # Add total cost info
        total_cost = sum(cost_data)
        plt.figtext(0.5, 0.02, f'Coût Total: {total_cost:.2f} TND',
                    ha='center', fontsize=10, style='italic')

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64

    except Exception as e:
        logger.error(f"Error creating cost distribution chart: {e}")
        return create_error_chart(f"Erreur Graphique Coûts:\n{str(e)}")


def create_actual_vs_predicted_chart(product, predictions):
    """
    Create a line chart comparing actual data vs predicted data
    """
    try:
        # Prepare data for comparison
        metrics = []
        actual_values = []
        predicted_values = []

        # Get actual data from product (if available)
        if hasattr(product, 'ml_predicted_energy_kwh') and product.ml_predicted_energy_kwh:
            metrics.append('Énergie (kWh)')
            actual_values.append(float(product.ml_predicted_energy_kwh))
            predicted_values.append(predictions.get(
                'production', {}).get('energy_consumption_kwh', 0))

        if hasattr(product, 'ml_predicted_water_liters') and product.ml_predicted_water_liters:
            metrics.append('Eau (L)')
            actual_values.append(float(product.ml_predicted_water_liters))
            predicted_values.append(predictions.get(
                'production', {}).get('water_consumption_liters', 0))

        if hasattr(product, 'ml_predicted_employees') and product.ml_predicted_employees:
            metrics.append('Employés')
            actual_values.append(float(product.ml_predicted_employees))
            predicted_values.append(predictions.get(
                'production', {}).get('total_employees', 0))

        # If no actual ML data, create comparison with traditional calculations
        if not metrics:
            # Use traditional oil production calculations - call the function directly since it's in the same file
            traditional_metrics = calculate_oil_production_metrics(
                product.quantity, product.quality, product.source
            )

        if traditional_metrics.get('success'):
            metrics = [
                'Coût Eau (TND)', 'Coût Énergie (TND)', 'Coût M.O. (TND)']
            actual_values = [
                traditional_metrics.get('cout_eau', 0),
                traditional_metrics.get('cout_energetique', 0),
                traditional_metrics.get('cout_main_oeuvre', 0)
            ]
            predicted_values = [
                predictions.get('costs', {}).get('water_cost_tnd', 0),
                predictions.get('costs', {}).get(
                    'electricity_cost_tnd', 0),
                predictions.get('costs', {}).get('labor_cost_tnd', 0)
            ]

        if not metrics or len(metrics) < 2:
            raise ValueError("Insufficient data for comparison")

        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(metrics))
        width = 0.35

        # Create bars
        bars1 = ax.bar(x - width/2, actual_values, width, label='Données Actuelles',
                       color='#2E86C1', alpha=0.8)
        bars2 = ax.bar(x + width/2, predicted_values, width, label='Prédictions ML',
                       color='#E74C3C', alpha=0.8)

        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        for bar in bars2:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax.set_xlabel('Métriques', fontsize=12)
        ax.set_ylabel('Valeurs', fontsize=12)
        ax.set_title('Comparaison: Données Actuelles vs Prédictions ML',
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Calculate and display accuracy
        if len(actual_values) == len(predicted_values):
            errors = [abs(a - p) / max(a, 1) * 100 for a,
                      p in zip(actual_values, predicted_values)]
            avg_accuracy = 100 - np.mean(errors)
            ax.text(0.02, 0.98, f'Précision Moyenne: {avg_accuracy:.1f}%',
                    transform=ax.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64

    except Exception as e:
        logger.error(f"Error creating actual vs predicted chart: {e}")
        return create_error_chart(f"Erreur Comparaison:\n{str(e)}")


def create_error_chart(error_message):
    """Create a simple error chart when chart generation fails"""
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, error_message, horizontalalignment='center',
                verticalalignment='center', transform=ax.transAxes,
                fontsize=12, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150,
                    bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()

        return image_base64
    except:
        return None


def calculate_oil_production_metrics(quantity, quality, source):
    """
    Calculate oil production metrics based on product inputs
    Enhanced version with better error handling
    """
    try:
        quantity = float(quantity) if quantity else 0
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        quality = str(quality).lower().strip() if quality else 'moyenne'

        # Enhanced mappings
        oil_yield_map = {
            'excellente': 0.20, 'excellent': 0.20,
            'bonne': 0.18, 'good': 0.18,
            'moyenne': 0.17, 'average': 0.17,
            'mauvaise': 0.15, 'poor': 0.15, 'bad': 0.15,
        }

        waste_coefficients = {
            'excellente': 0.82, 'excellent': 0.82,
            'bonne': 0.835, 'good': 0.835,
            'moyenne': 0.85, 'average': 0.85,
            'mauvaise': 0.875, 'poor': 0.875, 'bad': 0.875,
        }

        quality_price_map = {
            'excellente': 15.0, 'excellent': 15.0,
            'bonne': 12.0, 'good': 12.0,
            'moyenne': 10.0, 'average': 10.0,
            'mauvaise': 8.0, 'poor': 8.0, 'bad': 8.0,
        }

        oil_yield = oil_yield_map.get(quality, 0.17)
        waste_coefficient = waste_coefficients.get(quality, 0.85)
        oil_price_per_liter = quality_price_map.get(quality, 10.0)

        # Calculate metrics
        oil_quantity = quantity * oil_yield
        total_waste = quantity * waste_coefficient

        fitoura_percentage = 0.65
        dechet_fitoura = total_waste * fitoura_percentage
        dechet_margin = total_waste * (1 - fitoura_percentage)

        # Enhanced cost calculations with regional factors
        regional_factors = {
            'nord': 1.1, 'north': 1.1,
            'centre': 1.0, 'center': 1.0,
            'sud': 0.9, 'south': 0.9,
            'sfax': 1.05
        }

        source_lower = source.lower() if source else 'centre'
        regional_factor = 1.0
        for region, factor in regional_factors.items():
            if region in source_lower:
                regional_factor = factor
                break

        cout_main_oeuvre = quantity * 0.8 * regional_factor
        cout_eau = oil_quantity * 2.5 * regional_factor
        cout_energetique = quantity * 1.2 * regional_factor
        temps_pression = quantity * 0.02

        cout_total = cout_main_oeuvre + cout_eau + cout_energetique

        return {
            'qualite_oil': quality.title(),
            'quantite_oil': round(oil_quantity, 2),
            'dechet_fitoura': round(dechet_fitoura, 2),
            'dechet_margin': round(dechet_margin, 2),
            'prix_litre': oil_price_per_liter,
            'cout_main_oeuvre': round(cout_main_oeuvre, 2),
            'cout_eau': round(cout_eau, 2),
            'cout_energetique': round(cout_energetique, 2),
            'temps_pression': round(temps_pression, 2),
            'cout_total': round(cout_total, 2),
            'regional_factor': regional_factor,
            'success': True
        }

    except Exception as e:
        logger.error(f"Error calculating oil production metrics: {e}")
        return {'error': str(e), 'success': False}


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_prediction_pdf(request, product_id):
    """
    Generate enhanced PDF prediction report with charts
    """
    try:
        # Get the product
        try:
            product = get_object_or_404(Product, id=product_id)
        except:
            return Response({
                'error': 'Product not found',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)

        if not global_prediction_service.is_loaded:
            return Response({
                'error': 'ML service not available',
                'success': False
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Get enhanced predictions
        predictions = global_prediction_service.predict_costs_and_production(
            source=product.source or 'Centre',
            quantity=product.quantity,
            quality=product.quality
        )

        if not predictions:
            return Response({
                'error': 'Unable to generate predictions for this product',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Get traditional calculations for comparison
        traditional_metrics = calculate_oil_production_metrics(
            product.quantity, product.quality, product.source
        )

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        response[
            'Content-Disposition'] = f'attachment; filename="enhanced_prediction_report_product_{product.id}.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4,
                                topMargin=2*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=15,
            textColor=colors.darkgreen
        )

        # Title
        story.append(Paragraph(
            f"Rapport de Prédiction Avancé - Produit #{product.id}", title_style))
        story.append(Spacer(1, 20))

        # Product Information
        story.append(Paragraph("Informations du Produit", subtitle_style))

        product_info = [
            ['Propriété', 'Valeur'],
            ['ID Produit', str(product.id)],
            ['Quantité', f"{product.quantity} kg"],
            ['Qualité', product.quality],
            ['Source', product.source or 'Non spécifié'],
            ['Date de Création', product.created_at.strftime(
                '%Y-%m-%d %H:%M') if hasattr(product, 'created_at') else 'N/A']
        ]

        product_table = Table(product_info, colWidths=[6*cm, 8*cm])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ]))

        story.append(product_table)
        story.append(Spacer(1, 30))

        # Charts Section
        story.append(Paragraph("Analyses Graphiques", subtitle_style))

        charts_created = 0

        # 1. Waste Partition Chart
        if traditional_metrics and traditional_metrics.get('success'):
            try:
                fitoura = traditional_metrics.get('dechet_fitoura', 0)
                margin = traditional_metrics.get('dechet_margin', 0)

                if fitoura > 0 or margin > 0:
                    story.append(
                        Paragraph("Répartition des Déchets", styles['Heading3']))
                    waste_chart_base64 = create_waste_partition_chart(
                        fitoura, margin)

                    if waste_chart_base64:
                        waste_chart_img = Image(io.BytesIO(
                            base64.b64decode(waste_chart_base64)))
                        waste_chart_img.drawWidth = 400
                        waste_chart_img.drawHeight = 300
                        story.append(waste_chart_img)
                        story.append(Spacer(1, 20))
                        charts_created += 1
            except Exception as e:
                logger.warning(f"Could not create waste chart: {e}")

        # 2. Cost Distribution Chart
        if predictions and 'costs' in predictions:
            try:
                story.append(
                    Paragraph("Répartition des Coûts", styles['Heading3']))
                cost_chart_base64 = create_cost_distribution_chart(
                    predictions['costs'])

                if cost_chart_base64:
                    cost_chart_img = Image(io.BytesIO(
                        base64.b64decode(cost_chart_base64)))
                    cost_chart_img.drawWidth = 400
                    cost_chart_img.drawHeight = 300
                    story.append(cost_chart_img)
                    story.append(Spacer(1, 20))
                    charts_created += 1
            except Exception as e:
                logger.warning(f"Could not create cost chart: {e}")

        # 3. Actual vs Predicted Chart
        try:
            story.append(
                Paragraph("Comparaison: Données Actuelles vs Prédictions", styles['Heading3']))
            comparison_chart_base64 = create_actual_vs_predicted_chart(
                product, predictions)

            if comparison_chart_base64:
                comparison_chart_img = Image(io.BytesIO(
                    base64.b64decode(comparison_chart_base64)))
                comparison_chart_img.drawWidth = 500
                comparison_chart_img.drawHeight = 300
                story.append(comparison_chart_img)
                story.append(Spacer(1, 20))
                charts_created += 1
        except Exception as e:
            logger.warning(f"Could not create comparison chart: {e}")

        # ML Predictions Section
        if predictions:
            story.append(
                Paragraph("Prédictions Machine Learning", subtitle_style))

            # Cost predictions
            if 'costs' in predictions:
                story.append(
                    Paragraph("Prédictions de Coûts", styles['Heading3']))
                costs = predictions['costs']

                cost_data = [
                    ['Type de Coût', 'Montant (TND)'],
                    ['Coût Électricité',
                        f"{costs.get('electricity_cost_tnd', 0):.2f}"],
                    ['Coût Eau', f"{costs.get('water_cost_tnd', 0):.2f}"],
                    ['Coût Main d\'Œuvre',
                        f"{costs.get('labor_cost_tnd', 0):.2f}"],
                    ['Coût Total Opérationnel',
                        f"{costs.get('total_operational_cost_tnd', 0):.2f}"]
                ]

                cost_table = Table(cost_data, colWidths=[7*cm, 4*cm])
                cost_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                ]))

                story.append(cost_table)
                story.append(Spacer(1, 20))

            # Production predictions
            if 'production' in predictions:
                story.append(
                    Paragraph("Prédictions de Production", styles['Heading3']))
                production = predictions['production']

                production_data = [
                    ['Métrique de Production', 'Valeur Prédite'],
                    ['Score Qualité Huile',
                        f"{production.get('oil_quality_score', 0):.1f}/100"],
                    ['Quantité Huile',
                        f"{production.get('oil_quantity_tons', 0):.2f} tonnes"],
                    ['Temps de Traitement',
                        f"{production.get('processing_time_hours', 0):.1f} heures"],
                    ['Consommation Énergie',
                        f"{production.get('energy_consumption_kwh', 0):.1f} kWh"],
                    ['Consommation Eau',
                        f"{production.get('water_consumption_liters', 0):.1f} litres"],
                    ['Employés Requis',
                        f"{production.get('total_employees', 0)} employés"]
                ]

                production_table = Table(
                    production_data, colWidths=[7*cm, 4*cm])
                production_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.moccasin),
                ]))

                story.append(production_table)
                story.append(Spacer(1, 20))

        # Traditional Analysis Section
        if traditional_metrics and traditional_metrics.get('success'):
            story.append(Paragraph("Analyse Traditionnelle", subtitle_style))

            traditional_data = [
                ['Métrique', 'Valeur'],
                ['Quantité d\'Huile',
                    f"{traditional_metrics.get('quantite_oil', 0)} L"],
                ['Déchet Fitoura',
                    f"{traditional_metrics.get('dechet_fitoura', 0)} kg"],
                ['Déchet Margin',
                    f"{traditional_metrics.get('dechet_margin', 0)} kg"],
                ['Prix par Litre',
                    f"{traditional_metrics.get('prix_litre', 0)} TND"],
                ['Coût Main d\'Œuvre',
                    f"{traditional_metrics.get('cout_main_oeuvre', 0)} TND"],
                ['Coût Eau', f"{traditional_metrics.get('cout_eau', 0)} TND"],
                ['Coût Énergétique',
                    f"{traditional_metrics.get('cout_energetique', 0)} TND"],
                ['Coût Total',
                    f"{traditional_metrics.get('cout_total', 0)} TND"]
            ]

            traditional_table = Table(traditional_data, colWidths=[7*cm, 4*cm])
            traditional_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkslateblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.thistle),
            ]))

            story.append(traditional_table)
            story.append(Spacer(1, 30))

        # Summary section
        if charts_created > 0:
            story.append(Paragraph("Résumé de l'Analyse", subtitle_style))
            summary_text = f"""
            Ce rapport présente une analyse complète du produit #{product.id} incluant:
            
            • {charts_created} graphiques d'analyse visuelle
            • Prédictions ML avancées pour les coûts et la production
            • Comparaison avec les méthodes traditionnelles
            • Répartition détaillée des déchets et des coûts
            
            Les prédictions sont basées sur des modèles d'apprentissage automatique 
            entraînés sur des données historiques de production d'huile d'olive.
            """
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 20))

        # Footer
        story.append(Paragraph(
            "Rapport généré par le Service de Prédiction ML Avancé", styles['Normal']))
        story.append(Paragraph(
            f"Généré le: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(
            Paragraph(f"Utilisateur: {request.user.username}", styles['Normal']))

        # Build PDF
        doc.build(story)
        return response

    except Exception as e:
        logger.error(f"Error generating enhanced prediction PDF: {e}")
        return Response({
            'error': f'Failed to generate enhanced prediction PDF: {str(e)}',
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Additional utility function for chart validation
def validate_chart_data(data, chart_type):
    """
    Validate data before chart creation to prevent errors
    """
    try:
        if chart_type == 'waste':
            fitoura, margin = data
            return fitoura > 0 or margin > 0

        elif chart_type == 'cost':
            costs = data
            return any(costs.get(key, 0) > 0 for key in ['electricity_cost_tnd', 'water_cost_tnd', 'labor_cost_tnd'])

        elif chart_type == 'comparison':
            product, predictions = data
            # Check if we have either ML data or traditional data for comparison
            has_ml_data = any([
                hasattr(
                    product, 'ml_predicted_energy_kwh') and product.ml_predicted_energy_kwh,
                hasattr(
                    product, 'ml_predicted_water_liters') and product.ml_predicted_water_liters,
                hasattr(
                    product, 'ml_predicted_employees') and product.ml_predicted_employees
            ])

            has_predictions = predictions and (
                'costs' in predictions or 'production' in predictions)

            return has_ml_data or has_predictions

        return False

    except Exception as e:
        logger.warning(f"Error validating chart data for {chart_type}: {e}")
        return False


# Enhanced error handling for matplotlib
def safe_matplotlib_operation(operation_func, *args, **kwargs):
    """
    Safely execute matplotlib operations with proper cleanup
    """
    try:
        return operation_func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Matplotlib operation failed: {e}")
        plt.close('all')  # Clean up any open figures
        return None
    finally:
        # Ensure memory cleanup
        plt.clf()
        plt.cla()
