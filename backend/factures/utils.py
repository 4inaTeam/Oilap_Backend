from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import darkblue
import logging

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
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        return qr_buffer
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return None


def get_facture_products(facture):
    """Safely get products for a facture with detailed logging"""
    try:
        logger.info(f"Getting products for facture {facture.id}")

        # Check if facture has products attribute
        if not hasattr(facture, 'products'):
            logger.error(f"Facture {facture.id} has no 'products' attribute")
            return []

        # Get all products for this facture
        try:
            all_products = facture.products.all()
            logger.info(
                f"Found {all_products.count()} total products for facture {facture.id}")

            # Filter for done products
            done_products = all_products.filter(status='done')
            logger.info(
                f"Found {done_products.count()} done products for facture {facture.id}")

            # Log each product
            for product in done_products:
                logger.info(f"Product {product.id}: quality={product.quality}, "
                            f"quantity={product.quantity}, price={product.price}, "
                            f"status={product.status}, origine={getattr(product, 'origine', 'N/A')}")

            return list(done_products)

        except Exception as e:
            logger.error(
                f"Error querying products for facture {facture.id}: {str(e)}")
            return []

    except Exception as e:
        logger.error(f"Error in get_facture_products: {str(e)}")
        return []


def safe_decimal_conversion(value, default=Decimal('0.00')):
    """Safely convert a value to Decimal"""
    try:
        if value is None:
            return default
        return Decimal(str(value))
    except (ValueError, TypeError, Exception) as e:
        logger.warning(f"Error converting value {value} to Decimal: {e}")
        return default


def generate_facture_pdf(facture):
    """Generate professional PDF with proper data access and error handling"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm)
        story = []

        # Styles
        styles = getSampleStyleSheet()

        # Debug: Log facture information
        logger.info(f"Starting PDF generation for facture ID: {facture.id}")
        logger.info(
            f"Facture number: {getattr(facture, 'facture_number', 'N/A')}")
        logger.info(f"Facture client: {getattr(facture, 'client', 'N/A')}")

        # FORCE recalculate totals before PDF generation
        try:
            facture.calculate_totals()
            logger.info("Facture totals recalculated successfully")
        except Exception as e:
            logger.error(f"Error recalculating totals: {e}")

        # Refresh facture from database
        try:
            facture.refresh_from_db()
            logger.info("Facture refreshed from database")
        except Exception as e:
            logger.error(f"Error refreshing facture from database: {e}")

        # Get client information safely
        client_name = "N/A"
        client_email = "N/A"
        try:
            if hasattr(facture, 'client') and facture.client:
                if hasattr(facture.client, 'get_full_name'):
                    client_name = facture.client.get_full_name() or facture.client.username
                else:
                    client_name = facture.client.username
                client_email = getattr(facture.client, 'email', 'N/A')
                logger.info(
                    f"Client info - Name: {client_name}, Email: {client_email}")
        except Exception as e:
            logger.error(f"Error getting client info: {e}")

        # Get facture details safely
        facture_number = getattr(
            facture, 'facture_number', f'FAC-{facture.id}')
        created_at = getattr(facture, 'created_at', None)
        if created_at:
            created_date = created_at.strftime('%d %b %Y')
        else:
            from datetime import datetime
            created_date = datetime.now().strftime('%d %b %Y')

        # Company header
        header_data = [
            ['', 'Facture'],
            ['', 'Nom de l\'usine'],
            ['', 'REG: 12300012300'],
            ['', 'ma3melFoulen@gmail.com | +216 33 524 415'],
            ['', ''],
            ['', f'Client: {client_name}'],
            ['', f'Email: {client_email}'],
            [f'NUMÉRO DE FACTURE :', f'{facture_number}'],
            [f'DATE DE FACTURE :', created_date],
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

        # Products table with ENHANCED error handling
        product_data = [
            ['Produit', 'Quantité', 'Production', 'Prix Unitaire', 'Total']
        ]

        # Get facture totals safely
        total_amount = safe_decimal_conversion(
            getattr(facture, 'total_amount', 0))
        tva_amount = safe_decimal_conversion(getattr(facture, 'tva_amount', 0))
        final_total = safe_decimal_conversion(
            getattr(facture, 'final_total', 0))

        logger.info(
            f"Facture totals - Total: {total_amount}, TVA: {tva_amount}, Final: {final_total}")

        # Get products safely
        products = get_facture_products(facture)

        if products:
            logger.info(f"Processing {len(products)} products for PDF")

            for product in products:
                try:
                    # Get product data safely
                    quality = getattr(product, 'quality', 'N/A')
                    quantity = safe_decimal_conversion(
                        getattr(product, 'quantity', 0))
                    price = safe_decimal_conversion(
                        getattr(product, 'price', 0))
                    origine = getattr(product, 'origine', '')

                    # Calculate unit price
                    unit_price = price / \
                        quantity if quantity > 0 else Decimal('0')

                    # Calculate olive oil volume
                    olive_oil_volume = safe_decimal_conversion(
                        product.calculate_olive_oil_volume())

                    # Get quality display name
                    quality_display = quality
                    if hasattr(product, 'QUALITY_CHOICES'):
                        quality_display = dict(
                            product.QUALITY_CHOICES).get(quality, quality)

                    # Build product description
                    product_description = f'Qualité {quality_display}'
                    if origine:
                        product_description += f' - {origine}'

                    product_data.append([
                        product_description,
                        f'{quantity} Kg',
                        f'{olive_oil_volume:.2f} L',
                        f'{unit_price:.2f} DT',
                        f'{price:.2f} DT'
                    ])

                    logger.info(
                        f"Added product to PDF: {product_description}, Price: {price}")

                except Exception as e:
                    logger.error(
                        f"Error processing product {getattr(product, 'id', 'unknown')}: {e}")
                    product_data.append([
                        'Produit avec erreur',
                        '0 Kg',
                        '0 L',
                        '0.00 DT',
                        '0.00 DT'
                    ])
        else:
            logger.warning(f"No products found for facture {facture.id}")
            product_data.append([
                'Aucun produit',
                '0 Kg',
                '0 L',
                '0.00 DT',
                '0.00 DT'
            ])

        # Create products table
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

        # Signature and totals section
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

        # Generate QR code
        qr_data = f"Facture: {facture_number}\nMontant: {final_total:.2f} DT\nClient: {client_name}\nDate: {created_date}"
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

        logger.info(f"PDF generated successfully for facture {facture_number}")
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
        # Log initial state
        logger.info(f"Starting PDF generation for facture {facture.id}")
        logger.info(f"Force regenerate: {force_regenerate}")

        # Check if PDF already exists
        if hasattr(facture, 'pdf_url') and facture.pdf_url and not force_regenerate:
            logger.info(
                f"PDF already exists for facture {facture.id}: {facture.pdf_url}")
            return facture.pdf_url

        facture_number = getattr(
            facture, 'facture_number', f'FAC-{facture.id:04d}')
        logger.info(f"Generating PDF for facture {facture_number}")

        # Debug: Log facture data before PDF generation
        logger.info(
            f"Facture data - ID: {facture.id}, Client: {facture.client}")

        # Check products count
        try:
            if hasattr(facture, 'products'):
                products_count = facture.products.count()
                done_products_count = facture.products.filter(
                    status='done').count()
                logger.info(
                    f"Products count: {products_count}, Done products: {done_products_count}")
            else:
                logger.warning(
                    f"Facture {facture.id} has no products attribute")
        except Exception as e:
            logger.error(f"Error checking products count: {e}")

        # Generate PDF
        pdf_buffer = generate_facture_pdf(facture)
        if not pdf_buffer:
            logger.error("Failed to generate PDF buffer")
            return None

        logger.info(
            f"PDF buffer created successfully, size: {len(pdf_buffer.getvalue())} bytes")

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


