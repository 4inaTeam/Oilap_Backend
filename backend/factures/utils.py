from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import darkblue
from io import BytesIO
import os
from django.conf import settings
import cloudinary
import cloudinary.uploader
import cloudinary.api
import qrcode
import logging
import io
from decimal import Decimal

logger = logging.getLogger(__name__)


def generate_qr_code(data):
    """Generate QR code and return as BytesIO buffer"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=6,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        return qr_buffer
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return None


def generate_facture_pdf(facture):
    """Generate professional PDF with proper data access"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm)
        story = []

        # Styles
        styles = getSampleStyleSheet()

        # Debug: Log facture information
        logger.info(
            f"Generating PDF for facture ID: {facture.id}, Number: {getattr(facture, 'facture_number', 'N/A')}")

        # FORCE recalculate totals before PDF generation to ensure fresh data
        facture.calculate_totals()
        
        # Refresh facture from database to get latest calculated values
        facture.refresh_from_db()

        # Get client information safely
        client_name = "N/A"
        client_email = "N/A"
        if hasattr(facture, 'client') and facture.client:
            if hasattr(facture.client, 'get_full_name'):
                client_name = facture.client.get_full_name() or facture.client.username
            else:
                client_name = facture.client.username
            client_email = getattr(facture.client, 'email', 'N/A')

        logger.info(
            f"Client info - Name: {client_name}, Email: {client_email}")

        # Company header with REAL data
        header_data = [
            ['', 'Facture'],
            ['', 'Nom de l\'usine'],
            ['', 'REG: 12300012300'],
            ['', 'ma3melFoulen@gmail.com | +216 33 524 415'],
            ['', ''],
            ['', f'Client: {client_name}'],
            ['', f'Email: {client_email}'],
            [f'NUMÉRO DE FACTURE :', f'{facture.facture_number}'],
            [f'DATE DE FACTURE :', facture.created_at.strftime('%d %b %Y')],
        ]

        header_table = Table(header_data, colWidths=[3*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 16),
            ('FONTNAME', (1, 1), (1, 4), 'Helvetica'),
            ('FONTSIZE', (1, 1), (1, 4), 9),
            ('FONTNAME', (1, 5), (1, 6), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 5), (1, 6), 10),
            ('FONTNAME', (0, 7), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 7), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 30))

        # Products table with CORRECT data access
        product_data = [
            ['Produit', 'Quantité', 'Production', 'Prix Unitaire', 'Total']
        ]

        logger.info(
            f"Facture totals before PDF generation - Total: {facture.total_amount}, TVA: {facture.tva_amount}, Final: {facture.final_total}")

        # Access products correctly
        if hasattr(facture, 'products'):
            try:
                # Get only products that are 'done' and linked to this facture
                products = facture.products.filter(status='done')
                product_count = products.count()
                logger.info(
                    f"Found {product_count} done products for facture {facture.facture_number}")

                if product_count > 0:
                    for product in products:
                        logger.info(f"Processing product ID: {product.id}, Quality: {product.quality}, "
                                    f"Quantity: {product.quantity}, Price: {product.price}, Status: {product.status}")

                        quantity = product.quantity
                        # product.price is already the total price (base_price * quantity)
                        total_price = Decimal(str(product.price))

                        # Calculate unit price from total price and quantity
                        unit_price = total_price / \
                            quantity if quantity > 0 else Decimal('0')

                        # Get quality display name
                        quality_display = dict(product.QUALITY_CHOICES).get(
                            product.quality, product.quality)

                        # Build product description
                        product_description = f'Qualité {quality_display}'
                        if product.origine:
                            product_description += f' - {product.origine}'

                        product_data.append([
                            product_description,
                            f'{quantity} Kg',
                            f'{quantity} L',
                            f'{unit_price:.2f} DT',
                            f'{total_price:.2f} DT'
                        ])

                        logger.info(
                            f"Added product to PDF: {product_description}, Total: {total_price}")
                else:
                    logger.warning("No done products found for this facture")
                    product_data.append(
                        ['Aucun produit', '0 Kg', '0 L', '0.00 DT', '0.00 DT'])

            except Exception as e:
                logger.error(
                    f"Error accessing products: {str(e)}", exc_info=True)
                product_data.append(
                    ['Erreur produit', '0 Kg', '0 L', '0.00 DT', '0.00 DT'])
        else:
            logger.error("Facture object does not have 'products' attribute")
            product_data.append(
                ['Aucun produit trouvé', '0 Kg', '0 L', '0.00 DT', '0.00 DT'])

        product_table = Table(product_data, colWidths=[
                              2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(product_table)
        story.append(Spacer(1, 40))

        # Use the facture's calculated totals directly (NO CREDIT CARD FEE)
        total_amount = facture.total_amount
        tva_amount = facture.tva_amount
        final_total = facture.final_total  # This now excludes credit card fee

        logger.info(
            f"Using facture totals for PDF - Base: {total_amount}, TVA: {tva_amount}, Final: {final_total}")

        # Signature and totals section with REAL data (NO CREDIT CARD FEE SHOWN)
        signature_totals_data = [
            ['Signature', '', 'Total', f'{total_amount:.2f} DT'],
            ['', '', 'TVA', f'{tva_amount:.2f} DT'],
            ['', '', 'Prix Total:', f'{final_total:.2f} DT'],
        ]

        signature_table = Table(signature_totals_data, colWidths=[
                                2*inch, 1.5*inch, 1.5*inch, 1*inch])
        signature_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 12),
            ('FONTNAME', (2, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (2, 0), (-1, -1), 10),
            ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (2, -1), (-1, -1), 12),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (2, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (2, -1), (-1, -1), colors.lightgrey),
        ]))

        story.append(signature_table)
        story.append(Spacer(1, 40))

        # Payment instructions
        payment_info = """
        INSTRUCTIONS DE PAIEMENT
        
        Nom de l'usine
        Nom de la banque : ATB
        SWIFT/IBAN: NZ0201230012
        Numéro de compte: 12-1234-1234566-12
        
        Pour toute question, veuillez nous contacter : ma3melFoulen@gmail.com | +216 33 524 415
        """

        payment_para = Paragraph(payment_info, styles['Normal'])

        # Generate QR code with REAL facture data
        qr_data = f"Facture: {facture.facture_number}\nMontant: {final_total:.2f} DT\nClient: {client_name}\nDate: {facture.created_at.strftime('%Y-%m-%d')}"
        qr_buffer = generate_qr_code(qr_data)

        if qr_buffer:
            qr_image = RLImage(qr_buffer, width=1*inch, height=1*inch)
            footer_table = Table([[payment_para, qr_image]],
                                 colWidths=[4.5*inch, 1.5*inch])
            footer_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ]))
            story.append(footer_table)
        else:
            story.append(payment_para)

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        logger.info(
            f"PDF generated successfully for facture {facture.facture_number}")
        return buffer

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
        return None


def upload_pdf_to_cloudinary(pdf_buffer, public_id):
    """Upload PDF buffer to Cloudinary"""
    try:
        if not hasattr(settings, 'CLOUDINARY_STORAGE') and not cloudinary.config().cloud_name:
            logger.error("Cloudinary not configured properly")
            return None

        pdf_buffer.seek(0)

        response = cloudinary.uploader.upload(
            pdf_buffer.getvalue(),
            public_id=public_id,
            resource_type="raw",
            format="pdf",
            overwrite=True,
            folder="factures",
            tags=["facture", "pdf"],
            type="upload",
            invalidate=True,
        )

        logger.info(
            f"PDF uploaded to Cloudinary: {response.get('secure_url')}")
        return response
    except Exception as e:
        logger.error(f"Error uploading to Cloudinary: {str(e)}")
        return None


def generate_and_upload_facture_pdf(facture, force_regenerate=False):
    """Main function to generate PDF and upload to Cloudinary"""
    try:
        # Check if PDF already exists
        if hasattr(facture, 'pdf_url') and facture.pdf_url and not force_regenerate:
            logger.info(
                f"PDF already exists for facture {getattr(facture, 'facture_number', facture.id)}")
            return facture.pdf_url

        facture_number = getattr(
            facture, 'facture_number', f'FAC-{facture.id:04d}')
        logger.info(f"Generating PDF for facture {facture_number}")

        # Debug: Log facture data before PDF generation
        logger.info(f"Facture data - ID: {facture.id}, Client: {facture.client}, "
                    f"Total: {facture.total_amount}, Products count: {facture.products.count() if hasattr(facture, 'products') else 'N/A'}")

        # Generate PDF
        pdf_buffer = generate_facture_pdf(facture)
        if not pdf_buffer:
            logger.error("Failed to generate PDF buffer")
            return None

        # Upload to Cloudinary
        public_id = f"facture_{facture_number}_{facture.id}"
        upload_response = upload_pdf_to_cloudinary(pdf_buffer, public_id)

        if upload_response and upload_response.get('secure_url'):
            # Update facture with PDF URL
            facture.pdf_url = upload_response['secure_url']
            facture.pdf_public_id = upload_response['public_id']
            facture.save(update_fields=['pdf_url', 'pdf_public_id'])

            logger.info(
                f"PDF successfully generated and uploaded for facture {facture_number}")
            return upload_response['secure_url']
        else:
            logger.error("Failed to upload PDF to Cloudinary")
            return None

    except Exception as e:
        logger.error(
            f"Error generating and uploading PDF: {str(e)}", exc_info=True)
        return None


def delete_pdf_from_cloudinary(public_id):
    """Delete PDF from Cloudinary"""
    try:
        response = cloudinary.uploader.destroy(public_id, resource_type="raw")
        return response.get('result') == 'ok'
    except Exception as e:
        logger.error(f"Error deleting PDF from Cloudinary: {str(e)}")
        return False


def get_cloudinary_pdf_info(public_id):
    """Get PDF information from Cloudinary"""
    try:
        response = cloudinary.api.resource(public_id, resource_type="raw")
        return response
    except Exception as e:
        logger.error(f"Error getting PDF info from Cloudinary: {str(e)}")
        return None


def add_product_and_update_facture_pdf(facture, product):
    """
    Helper to add a product to a facture and regenerate/upload the PDF.
    Call this after saving the product to the facture.
    """
    return facture.refresh_pdf()