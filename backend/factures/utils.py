from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from io import BytesIO
import os
from django.conf import settings
from datetime import datetime
import cloudinary
import cloudinary.uploader
import cloudinary.api
from django.core.files.uploadedfile import InMemoryUploadedFile
import tempfile
import qrcode
from decimal import Decimal
import logging

# Set up logging
logger = logging.getLogger(__name__)


def generate_qr_code(data):
    """Generate QR code and return as BytesIO"""
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

        # Save to BytesIO
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)

        return qr_buffer
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return None


def generate_facture_pdf(facture):
    """Generate PDF for facture and return BytesIO buffer"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1 *
                                inch, rightMargin=0.5*inch, leftMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_RIGHT
        )

        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )

        story.append(Paragraph("Facture", title_style))

        company_info = """
        <b>Nom de l'usine</b><br/>
        REG: 123000123000<br/>
        ma3melFoulen@gmail.com | +216 33 524 415
        """
        story.append(Paragraph(company_info, header_style))
        story.append(Spacer(1, 20))

        # Safe access to client info
        client_name = getattr(facture.client, 'username', 'N/A') if facture.client else 'N/A'
        
        client_info_data = [
            ['', 'Nom de client'],
            ['NUMÉRO DE FACTURE :', str(facture.facture_number)],
            ['DATE DE FACTURE :', facture.created_at.strftime('%d %b %Y')],
        ]

        client_table = Table(client_info_data, colWidths=[3*inch, 2*inch])
        client_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
        ]))

        story.append(client_table)
        story.append(Spacer(1, 30))

        # Products table with better error handling
        products_data = [['Produit', 'Quantité',
                          'Production', 'Prix Unitaire', 'Total']]

        # Check if facture has products
        if hasattr(facture, 'products') and facture.products.exists():
            products = facture.products.filter(status='done')
            
            if products.exists():
                for product in products:
                    try:
                        # Safe decimal conversion with error handling
                        quantity = Decimal(str(product.quantity)) if product.quantity else Decimal('0')
                        price = Decimal(str(product.price)) if product.price else Decimal('0')
                        
                        if quantity > 0:
                            unit_price = price / quantity
                        else:
                            unit_price = price
                            
                        total_price = price  # Total price is already the total, not price * quantity

                        # Safe access to product attributes
                        product_name = getattr(product, 'quality', 'N/A')
                        if hasattr(product_name, 'title'):
                            product_name = product_name.title()
                        else:
                            product_name = str(product_name)

                        products_data.append([
                            product_name,
                            f"{quantity} Kg",
                            "120 L",  # You might want to make this dynamic
                            f"{unit_price:.2f} DT",
                            f"{total_price:.2f} DT"
                        ])
                    except Exception as e:
                        logger.error(f"Error processing product {product.id}: {str(e)}")
                        continue
            else:
                products_data.append(['Aucun produit trouvé', '', '', '', ''])
        else:
            products_data.append(['Aucun produit trouvé', '', '', '', ''])

        products_table = Table(products_data, colWidths=[
                               1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        products_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        story.append(products_table)
        story.append(Spacer(1, 30))

        # Create QR code with error handling
        qr_data = f"Facture: {facture.facture_number}\nClient: {client_name}\nMontant: {facture.final_total} DT\nDate: {facture.created_at.strftime('%d/%m/%Y')}"
        qr_buffer = generate_qr_code(qr_data)

        # Save QR code to temporary file
        qr_temp_path = None
        qr_image = None

        if qr_buffer:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                    tmp_file.write(qr_buffer.getvalue())
                    qr_temp_path = tmp_file.name

                qr_image = Image(qr_temp_path, width=1.5*inch, height=1.5*inch)
            except Exception as e:
                logger.error(f"Error creating QR code image: {str(e)}")

        # Create signature and totals section with QR code
        # Safe access to facture financial fields
        total_amount = getattr(facture, 'total_amount', 0) or 0
        tva_amount = getattr(facture, 'tva_amount', 0) or 0
        credit_card_fee = getattr(facture, 'credit_card_fee', 0) or 0
        final_total = getattr(facture, 'final_total', 0) or 0
        
        totals_data = [
            ['Total', f"{total_amount:.2f} DT"],
            ['TVA', f"{tva_amount:.2f} DT"],
            ['Frais de carte de crédit (si utilisée) :', f"{credit_card_fee:.2f} DT"],
            ['', ''],
            ['Prix Total:', f"{final_total:.2f} DT"],
        ]

        # Create totals table
        totals_table = Table(totals_data, colWidths=[3*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (1, -1), (1, -1), 1, colors.black),
            ('LINEBELOW', (1, -1), (1, -1), 1, colors.black),
            ('GRID', (0, 0), (1, -2), 1, colors.black),
            ('BACKGROUND', (0, 0), (1, -2), colors.lightgrey),
        ]))

        # Combine signature, QR code, and totals
        if qr_image:
            signature_section_data = [
                ['Signature', totals_table],
                [qr_image, '']
            ]

            signature_section = Table(
                signature_section_data, colWidths=[2.5*inch, 4*inch])
            signature_section.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 0), (0, 0), 12),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ]))

            story.append(signature_section)
        else:
            # Fallback without QR code
            story.append(Paragraph("Signature", styles['Normal']))
            story.append(Spacer(1, 20))
            story.append(totals_table)

        # Clean up temporary QR code file
        if qr_temp_path and os.path.exists(qr_temp_path):
            try:
                os.unlink(qr_temp_path)
            except Exception as e:
                logger.error(f"Error deleting temp QR file: {str(e)}")

        story.append(Spacer(1, 50))

        payment_info = """
        <b>INSTRUCTIONS DE PAIEMENT</b><br/>
        Nom de l'usine<br/>
        Nom de la banque : ATB<br/>
        SWIFT/IBAN: NZ0201230012<br/>
        Numéro de compte: 12-1234-1234556-12<br/><br/>
        Pour toute question, veuillez nous contacter : ma3melFoulen@gmail.com | +216 33 524 415
        """

        payment_style = ParagraphStyle(
            'PaymentStyle',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_LEFT
        )

        story.append(Paragraph(payment_info, payment_style))

        # Build the PDF
        doc.build(story)
        buffer.seek(0)
        logger.info(f"PDF generated successfully for facture {facture.facture_number}")
        return buffer

    except Exception as e:
        logger.error(f"Error generating PDF for facture {facture.id}: {str(e)}")
        raise


def upload_pdf_to_cloudinary(pdf_buffer, public_id):
    """Upload PDF buffer to Cloudinary"""
    try:
        # Ensure cloudinary is configured
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
            tags=["facture", "pdf"]
        )

        logger.info(f"PDF uploaded to Cloudinary: {response.get('secure_url')}")
        return response
    except Exception as e:
        logger.error(f"Error uploading to Cloudinary: {str(e)}")
        return None


def generate_and_upload_facture_pdf(facture, force_regenerate=False):
    """Generate PDF and upload to Cloudinary"""
    try:
        # Check if PDF already exists and we don't want to force regenerate
        if hasattr(facture, 'pdf_url') and facture.pdf_url and not force_regenerate:
            logger.info(f"PDF already exists for facture {facture.facture_number}")
            return facture.pdf_url

        logger.info(f"Generating PDF for facture {facture.facture_number}")
        pdf_buffer = generate_facture_pdf(facture)

        public_id = f"facture_{facture.facture_number}_{facture.id}"

        upload_response = upload_pdf_to_cloudinary(pdf_buffer, public_id)

        if upload_response and upload_response.get('secure_url'):
            # Update facture with PDF info
            facture.pdf_url = upload_response['secure_url']
            facture.pdf_public_id = upload_response['public_id']
            facture.save(update_fields=['pdf_url', 'pdf_public_id'])

            logger.info(f"PDF successfully generated and uploaded for facture {facture.facture_number}")
            return upload_response['secure_url']
        else:
            logger.error("Failed to upload PDF to Cloudinary")
            return None

    except Exception as e:
        logger.error(f"Error generating and uploading PDF: {str(e)}")
        return None


def delete_pdf_from_cloudinary(public_id):
    """Delete PDF from Cloudinary"""
    try:
        response = cloudinary.uploader.destroy(
            public_id,
            resource_type="raw"
        )
        return response.get('result') == 'ok'
    except Exception as e:
        logger.error(f"Error deleting PDF from Cloudinary: {str(e)}")
        return False


def get_cloudinary_pdf_info(public_id):
    """Get information about PDF from Cloudinary"""
    try:
        response = cloudinary.api.resource(
            public_id,
            resource_type="raw"
        )
        return response
    except Exception as e:
        logger.error(f"Error getting PDF info from Cloudinary: {str(e)}")
        return None