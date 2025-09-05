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
import logging
import matplotlib
matplotlib.use('Agg')

logger = logging.getLogger(__name__)


def calculate_oil_production_metrics(quantity, quality, source):
    """
    Calculate oil production metrics based on product inputs
    Fixed to handle missing or invalid inputs gracefully
    """
    try:
        # Ensure quantity is numeric and positive
        quantity = float(quantity) if quantity else 0
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        # Normalize quality input
        if not quality:
            quality = 'moyenne'
        quality = str(quality).lower().strip()

        # Base calculations based on product model constants
        oil_yield_map = {
            'excellente': 0.20,
            'excellent': 0.20,  # Alternative spelling
            'bonne': 0.18,
            'good': 0.18,
            'moyenne': 0.17,
            'average': 0.17,
            'mauvaise': 0.15,
            'poor': 0.15,
            'bad': 0.15,
        }

        waste_coefficients = {
            'excellente': 0.82,
            'excellent': 0.82,
            'bonne': 0.835,
            'good': 0.835,
            'moyenne': 0.85,
            'average': 0.85,
            'mauvaise': 0.875,
            'poor': 0.875,
            'bad': 0.875,
        }

        quality_price_map = {
            'excellente': 15.0,
            'excellent': 15.0,
            'bonne': 12.0,
            'good': 12.0,
            'moyenne': 10.0,
            'average': 10.0,
            'mauvaise': 8.0,
            'poor': 8.0,
            'bad': 8.0,
        }

        # Get values with defaults
        oil_yield = oil_yield_map.get(quality, 0.17)
        waste_coefficient = waste_coefficients.get(quality, 0.85)
        oil_price_per_liter = quality_price_map.get(quality, 10.0)

        # Calculate basic metrics
        oil_quantity = quantity * oil_yield
        total_waste = quantity * waste_coefficient

        # Split waste into margin (fitoura) and other waste
        # Fitoura is typically 60-70% of total waste
        fitoura_percentage = 0.65
        dechet_fitoura = total_waste * fitoura_percentage
        dechet_margin = total_waste * (1 - fitoura_percentage)

        # Cost calculations (estimated values - can be adjusted based on actual costs)
        cout_main_oeuvre = quantity * 0.8  # 0.8 DT per kg
        cout_eau = oil_quantity * 2.5  # 2.5 DT per liter of oil
        cout_energetique = quantity * 1.2  # 1.2 DT per kg
        # 0.02 hours per kg (continuous method)
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
            'success': True
        }

    except Exception as e:
        logger.error(f"Error calculating oil production metrics: {e}")
        return {
            'error': str(e),
            'success': False
        }


def create_pie_chart(data, labels, title, colors_list=None):
    """
    Create a pie chart and return it as base64 image
    Fixed to handle empty data and encoding issues
    """
    try:
        # Validate inputs
        if not data or not labels or len(data) != len(labels):
            raise ValueError("Invalid data or labels for pie chart")

        # Filter out zero or negative values
        filtered_data = []
        filtered_labels = []
        for d, l in zip(data, labels):
            if d > 0:
                filtered_data.append(d)
                filtered_labels.append(l)

        if not filtered_data:
            raise ValueError("No positive data values for pie chart")

        # Create figure
        plt.figure(figsize=(8, 6))
        fig, ax = plt.subplots(figsize=(8, 6))

        if colors_list is None:
            colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1',
                           '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']

        # Ensure we have enough colors
        while len(colors_list) < len(filtered_data):
            colors_list.extend(colors_list)

        wedges, texts, autotexts = ax.pie(
            filtered_data,
            labels=filtered_labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors_list[:len(filtered_data)]
        )

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        # Make percentage text bold and white
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)

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
        logger.error(f"Error creating pie chart: {e}")
        # Create a simple error chart
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, f'Chart Error:\n{str(e)}',
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12)
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


def create_line_chart(real_data, predicted_data, error_margins, labels, title):
    """
    Create a line chart comparing real vs predicted data with error margins
    Fixed to handle missing data and mismatched array lengths
    """
    try:
        # Validate inputs
        if not all([real_data, predicted_data, labels]):
            raise ValueError("Missing required data for line chart")

        # Ensure all arrays have the same length
        min_length = min(len(real_data), len(predicted_data), len(labels))
        if min_length == 0:
            raise ValueError("Empty data arrays")

        real_data = real_data[:min_length]
        predicted_data = predicted_data[:min_length]
        labels = labels[:min_length]

        if error_margins:
            error_margins = error_margins[:min_length]
        else:
            # Create default error margins if not provided
            error_margins = [abs(r - p) * 0.1 for r,
                             p in zip(real_data, predicted_data)]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(labels))

        # Plot real data
        ax.plot(x, real_data, 'o-', label='Données Réelles',
                color='#2E86C1', linewidth=2, markersize=8)

        # Plot predicted data
        ax.plot(x, predicted_data, 's-', label='Données Prédites',
                color='#E74C3C', linewidth=2, markersize=8)

        # Add error margins as shaded area
        lower_bounds = np.array(predicted_data) - np.array(error_margins)
        upper_bounds = np.array(predicted_data) + np.array(error_margins)

        ax.fill_between(x, lower_bounds, upper_bounds,
                        alpha=0.3, color='#E74C3C', label='Marge d\'Erreur')

        ax.set_xlabel('Points de Données', fontsize=12)
        ax.set_ylabel('Valeurs', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3)

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
        logger.error(f"Error creating line chart: {e}")
        # Create error chart
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, f'Chart Error:\n{str(e)}',
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12)
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


def create_prediction_table(inputs, outputs):
    """
    Create the main prediction table in key-value format for better readability
    Fixed to handle missing data gracefully
    """
    try:
        table_data = []

        # Safely get values with defaults
        def safe_get(d, key, default="N/A"):
            return str(d.get(key, default)) if isinstance(d, dict) else str(default)

        # Section headers and data in key-value pairs
        sections = [
            ("DONNÉES D'ENTRÉE", [
                ("Quantité", f"{safe_get(inputs, 'quantite')} kg"),
                ("Qualité", safe_get(inputs, 'qualite')),
                ("Source", safe_get(inputs, 'source')),
                ("Type de Presse", safe_get(inputs, 'type_presse', 'Continue')),
            ]),
            ("RÉSULTATS DE PRODUCTION", [
                ("Qualité de l'Huile", safe_get(outputs, 'qualite_oil')),
                ("Quantité d'Huile", f"{safe_get(outputs, 'quantite_oil')} L"),
                ("Déchet Fitoura",
                 f"{safe_get(outputs, 'dechet_fitoura')} kg"),
                ("Déchet Margin", f"{safe_get(outputs, 'dechet_margin')} kg"),
            ]),
            ("ANALYSE FINANCIÈRE", [
                ("Prix par Litre", f"{safe_get(outputs, 'prix_litre')} DT"),
                ("Coût Main d'Œuvre",
                 f"{safe_get(outputs, 'cout_main_oeuvre')} DT"),
                ("Coût Eau", f"{safe_get(outputs, 'cout_eau')} DT"),
                ("Coût Énergétique",
                 f"{safe_get(outputs, 'cout_energetique')} DT"),
                ("Temps de Pression",
                 f"{safe_get(outputs, 'temps_pression')} h"),
                ("Coût Total", f"{safe_get(outputs, 'cout_total')} DT"),
            ])
        ]

        # Create table with 2 columns: Key and Value
        for section_title, section_data in sections:
            # Add section header
            table_data.append([section_title, ""])

            # Add key-value pairs for this section
            for key, value in section_data:
                table_data.append([key, str(value)])

            # Add empty row for spacing between sections
            table_data.append(["", ""])

        # Remove the last empty row
        if table_data and table_data[-1] == ["", ""]:
            table_data.pop()

        return table_data

    except Exception as e:
        logger.error(f"Error creating prediction table: {e}")
        return [["Erreur", f"Impossible de créer le tableau: {str(e)}"]]


def generate_prediction_pdf_with_ml_data(product_id, product, predictions):
    """
    Generate PDF report using ML predictions from the enhanced service
    Fixed to work with the actual views.py ML prediction structure
    """
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=2*cm, bottomMargin=2*cm)

        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )

        story = []

        # Title
        story.append(
            Paragraph(f"Rapport de Prédiction ML - Produit #{product_id}", title_style))
        story.append(Spacer(1, 20))

        # Product Information Section
        story.append(Paragraph("Informations du Produit", styles['Heading2']))

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

        # ML Predictions Section
        if predictions:
            story.append(
                Paragraph("Prédictions Machine Learning", styles['Heading2']))

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

        # Create charts if we have sufficient data
        try:
            charts_created = False

            # Cost breakdown pie chart
            if predictions and 'costs' in predictions:
                costs = predictions['costs']
                cost_values = [
                    costs.get('electricity_cost_tnd', 0),
                    costs.get('water_cost_tnd', 0),
                    costs.get('labor_cost_tnd', 0)
                ]
                cost_labels = ['Électricité', 'Eau', 'Main d\'Œuvre']

                if sum(cost_values) > 0:
                    story.append(
                        Paragraph("Répartition des Coûts", styles['Heading3']))
                    pie_chart_base64 = create_pie_chart(
                        cost_values,
                        cost_labels,
                        "Répartition des Coûts Opérationnels"
                    )

                    if pie_chart_base64:
                        pie_chart_img = Image(io.BytesIO(
                            base64.b64decode(pie_chart_base64)))
                        pie_chart_img.drawWidth = 200
                        pie_chart_img.drawHeight = 150
                        story.append(pie_chart_img)
                        story.append(Spacer(1, 20))
                        charts_created = True

        except Exception as e:
            logger.warning(f"Could not create charts: {e}")

        # Footer
        story.append(Paragraph(
            "Rapport généré par le Service de Prédiction ML Avancé", styles['Normal']))
        story.append(Paragraph(
            f"Généré le: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        return buffer

    except Exception as e:
        logger.error(f"Error generating ML prediction PDF: {e}")
        # Create error PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph("Erreur de Génération PDF", styles['Title']),
            Paragraph(f"Une erreur s'est produite: {str(e)}", styles['Normal'])
        ]
        doc.build(story)
        buffer.seek(0)
        return buffer


def create_sample_data_for_testing():
    """
    Create sample data for testing the charts and functions
    """
    return {
        'real_data': [85, 92, 78, 88, 95],
        'predicted_data': [82, 89, 81, 85, 93],
        'error_margins': [3, 4, 3.5, 3, 2.5],
        'labels': ['Lot 1', 'Lot 2', 'Lot 3', 'Lot 4', 'Lot 5'],
        'sample_inputs': {
            'quantite': 1000,
            'qualite': 'bonne',
            'source': 'Centre',
            'type_presse': 'Continue'
        }
    }


def validate_pdf_inputs(inputs, outputs):
    """
    Validate inputs and outputs for PDF generation
    """
    errors = []

    # Validate inputs
    required_input_fields = ['quantite', 'qualite']
    for field in required_input_fields:
        if not inputs or field not in inputs or not inputs[field]:
            errors.append(f"Missing required input field: {field}")

    # Validate outputs
    if not outputs or not isinstance(outputs, dict):
        errors.append("Missing or invalid outputs data")
    elif not outputs.get('success', False):
        errors.append(
            f"Output calculation failed: {outputs.get('error', 'Unknown error')}")

    return errors
