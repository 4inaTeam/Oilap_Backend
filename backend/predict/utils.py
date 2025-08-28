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
import matplotlib
matplotlib.use('Agg')


def calculate_oil_production_metrics(quantity, quality, source):
    """Calculate oil production metrics based on product inputs"""
    
    # Base calculations based on product model constants
    oil_yield_map = {
        'excellente': 0.20,
        'bonne': 0.18,
        'moyenne': 0.17,
        'mauvaise': 0.15,
    }
    
    waste_coefficients = {
        'excellente': 0.82,
        'bonne': 0.835,
        'moyenne': 0.85,
        'mauvaise': 0.875,
    }
    
    quality_price_map = {
        'excellente': 15,
        'bonne': 12,
        'moyenne': 10,
        'mauvaise': 8,
    }
    
    # Calculate basic metrics
    oil_yield = oil_yield_map.get(quality.lower(), 0.17)
    oil_quantity = quantity * oil_yield
    waste_coefficient = waste_coefficients.get(quality.lower(), 0.85)
    total_waste = quantity * waste_coefficient
    
    # Split waste into margin (fitoura) and other waste
    # Fitoura is typically 60-70% of total waste
    fitoura_percentage = 0.65
    dechet_fitoura = total_waste * fitoura_percentage
    dechet_margin = total_waste * (1 - fitoura_percentage)
    
    # Calculate costs and pricing
    oil_price_per_liter = quality_price_map.get(quality.lower(), 10)
    
    # Cost calculations (estimated values)
    cout_main_oeuvre = quantity * 0.8  # 0.8 DT per kg
    cout_eau = oil_quantity * 2.5  # 2.5 DT per liter of oil
    cout_energetique = quantity * 1.2  # 1.2 DT per kg
    temps_pression = quantity * 0.02  # 0.02 hours per kg (continuous method)
    
    cout_total = cout_main_oeuvre + cout_eau + cout_energetique
    
    return {
        'qualite_oil': quality,
        'quantite_oil': round(oil_quantity, 2),
        'dechet_fitoura': round(dechet_fitoura, 2),
        'dechet_margin': round(dechet_margin, 2),
        'prix_litre': oil_price_per_liter,
        'cout_main_oeuvre': round(cout_main_oeuvre, 2),
        'cout_eau': round(cout_eau, 2),
        'cout_energetique': round(cout_energetique, 2),
        'temps_pression': round(temps_pression, 2),
        'cout_total': round(cout_total, 2)
    }


def create_pie_chart(data, labels, title, colors_list=None):
    """Create a pie chart and return it as base64 image"""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    if colors_list is None:
        colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']
    
    wedges, texts, autotexts = ax.pie(
        data, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        colors=colors_list[:len(data)]
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
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64


def create_line_chart(real_data, predicted_data, error_margins, labels, title):
    """Create a line chart comparing real vs predicted data with error margins"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(labels))
    
    # Plot real data
    ax.plot(x, real_data, 'o-', label='Données Réelles', color='#2E86C1', linewidth=2, markersize=8)
    
    # Plot predicted data
    ax.plot(x, predicted_data, 's-', label='Données Prédites', color='#E74C3C', linewidth=2, markersize=8)
    
    # Add error margins as shaded area
    ax.fill_between(x, 
                   np.array(predicted_data) - np.array(error_margins),
                   np.array(predicted_data) + np.array(error_margins),
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
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64


def create_prediction_table(inputs, outputs):
    """Create the main prediction table in key-value format for better readability"""
    table_data = []
    
    # Section headers and data in key-value pairs
    sections = [
        ("DONNÉES D'ENTRÉE", [
            ("Quantité", f"{inputs['quantite']} kg"),
            ("Qualité", inputs['qualite']),
            ("Source", inputs['source']),
            ("Type de Presse", inputs['type_presse']),
        ]),
        ("RÉSULTATS DE PRODUCTION", [
            ("Qualité de l'Huile", outputs['qualite_oil']),
            ("Quantité d'Huile", f"{outputs['quantite_oil']} L"),
            ("Déchet Fitoura", f"{outputs['dechet_fitoura']} kg"),
            ("Déchet Margin", f"{outputs['dechet_margin']} kg"),
        ]),
        ("ANALYSE FINANCIÈRE", [
            ("Prix par Litre", f"{outputs['prix_litre']} DT"),
            ("Coût Main d'Œuvre", f"{outputs['cout_main_oeuvre']} DT"),
            ("Coût Eau", f"{outputs['cout_eau']} DT"),
            ("Coût Énergétique", f"{outputs['cout_energetique']} DT"),
            ("Temps de Pression", f"{outputs['temps_pression']} h"),
            ("Coût Total", f"{outputs['cout_total']} DT"),
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


def generate_prediction_pdf(product_id, inputs, outputs, charts_data):
    """Generate the complete PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    
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
    story.append(Paragraph(f"Rapport de Prédiction - Produit #{product_id}", title_style))
    story.append(Spacer(1, 20))
    
    # Main prediction table
    table_data = create_prediction_table(inputs, outputs)
    
    # Create table with styling - 2 columns: Key and Value
    table = Table(table_data, colWidths=[8*cm, 6*cm])
    
    # Create dynamic styling based on table content
    table_styles = [
        # Basic table formatting
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        
        # Key column (left) - bold and left aligned
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        
        # Value column (right) - normal weight and right aligned
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]
    
    # Add section header styling
    row_index = 0
    for i, row in enumerate(table_data):
        if row[1] == "":  # This is a section header
            table_styles.extend([
                ('BACKGROUND', (0, i), (-1, i), colors.darkblue),
                ('TEXTCOLOR', (0, i), (-1, i), colors.whitesmoke),
                ('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'),
                ('FONTSIZE', (0, i), (-1, i), 12),
                ('ALIGN', (0, i), (-1, i), 'CENTER'),
                ('SPAN', (0, i), (1, i)),  # Merge both columns for section headers
            ])
        elif row[0] == "" and row[1] == "":  # Empty spacing row
            table_styles.extend([
                ('BACKGROUND', (0, i), (-1, i), colors.white),
                ('FONTSIZE', (0, i), (-1, i), 6),
            ])
        else:  # Regular key-value row
            # Alternate row colors for better readability
            bg_color = colors.lightgrey if (i % 4) < 2 else colors.white
            table_styles.extend([
                ('BACKGROUND', (0, i), (-1, i), bg_color),
            ])
    
    table.setStyle(TableStyle(table_styles))
    
    story.append(table)
    story.append(Spacer(1, 30))
    
    # Charts section
    story.append(Paragraph("Analyses Graphiques", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # First pie chart - Margin vs Fitoura
    if 'pie_chart_1' in charts_data:
        pie_chart_1 = Image(io.BytesIO(base64.b64decode(charts_data['pie_chart_1'])))
        pie_chart_1.drawWidth = 200
        pie_chart_1.drawHeight = 150
        story.append(pie_chart_1)
        story.append(Spacer(1, 20))
    
    # Second pie chart - Costs breakdown
    if 'pie_chart_2' in charts_data:
        pie_chart_2 = Image(io.BytesIO(base64.b64decode(charts_data['pie_chart_2'])))
        pie_chart_2.drawWidth = 200
        pie_chart_2.drawHeight = 150
        story.append(pie_chart_2)
        story.append(Spacer(1, 20))
    
    # Line chart - Real vs Predicted
    if 'line_chart' in charts_data:
        line_chart = Image(io.BytesIO(base64.b64decode(charts_data['line_chart'])))
        line_chart.drawWidth = 300
        line_chart.drawHeight = 180
        story.append(line_chart)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def create_sample_data():
    """Create sample data for testing the charts"""
    # Sample data for line chart (real vs predicted comparison)
    real_data = [85, 92, 78, 88, 95]
    predicted_data = [82, 89, 81, 85, 93]
    error_margins = [3, 4, 3.5, 3, 2.5]
    labels = ['Batch 1', 'Batch 2', 'Batch 3', 'Batch 4', 'Batch 5']
    
    return {
        'real_data': real_data,
        'predicted_data': predicted_data,
        'error_margins': error_margins,
        'labels': labels
    }