from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, jsonify, session
from flask_login import login_required, current_user
from translations import trans
import utils
from bson import ObjectId
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional
import logging
import io

logger = logging.getLogger(__name__)

RECEIPTS_TRANSLATIONS = {
    'en': {
        'receipts_dashboard': 'Sales Income',
        'receipts_list': 'Sales Income List',
        # Receipts
        'receipts_payer_name': 'Customer Name',
        'receipts_add_receipt': 'Record Sale',
        'receipts_edit_receipt': 'Edit Sale',
        'receipts_tooltip': 'View and manage your sales income',
        'receipts_delete_receipt': 'Delete Sale Record',
        'receipts_receipt_number': 'Sale Reference Number',
        'receipts_add_money_in': 'Record Sales Income',
        'receipts_insufficient_coins': 'Insufficient coins to record sale',
        'receipts_money_in': 'Sales Income',
        'receipts_money_in_subtext': 'Track your sales revenue',
        'receipts_no_money_in': 'No sales income recorded',
        'receipts_date_issued': 'Date Issued',
        'receipts_customer': 'Customer',
        'receipts_amount': 'Sale Amount',
        'receipts_payment_method': 'Payment Method',
        'receipts_description': 'Track sales revenue',
        'receipts_items': 'Items',
        'receipts_quantity': 'Quantity',
        'receipts_unit_price': 'Unit Price',
        'receipts_total': 'Total',
        'receipts_subtotal': 'Subtotal',
        'receipts_tax': 'Tax',
        'receipts_discount': 'Discount',
        'receipts_status': 'Status',
        'receipts_paid': 'Paid',
        'receipts_pending': 'Pending',
        'receipts_overdue': 'Overdue',
        'receipts_cancelled': 'Cancelled',
        'receipts_void': 'Void',
        'receipts_print': 'Print Sales Receipt',
        'receipts_email': 'Email Sales Receipt',
        'receipts_duplicate': 'Duplicate Sale Record',
        'receipts_refund': 'Refund',
        'receipts_notes': 'Notes',
        'receipts_terms': 'Terms & Conditions',
        'receipts_signature': 'Signature',
        'receipts_company_info': 'Company Information',
        'receipts_receipt_created': 'Sale recorded successfully',
        'receipts_receipt_updated': 'Sale updated successfully',
        'receipts_receipt_deleted': 'Sale record deleted successfully',
        'receipts_confirm_delete': 'Are you sure you want to delete this sale record?',
        'receipts_no_receipts': 'No sales income found',
        'receipts_search_receipts': 'Search sales...',
        'receipts_total_receipts': 'Total Sales',
        'receipts_total_amount': 'Total Revenue',
        'receipts_today_receipts': 'Today\'s Sales',
        'receipts_monthly_receipts': 'Monthly Sales',
    },
    'ha': {
        'receipts_dashboard': 'Kudaden Sayarwa',
        'receipts_list': 'Jerin Kudaden Sayarwa',
        'receipts_add_receipt': 'Rubuta Sayarwa',
        'receipts_edit_receipt': 'Gyara Sayarwa',
        'receipts_delete_receipt': 'Goge Sayarwa',
        'receipts_receipt_number': 'Lambar Sayarwa',
        'receipts_date_issued': 'Ranar Bayarwa',
        'receipts_customer': 'Abokin Ciniki',
        'receipts_amount': 'Adadin Sayarwa',
        'receipts_payment_method': 'Hanyar Biya',
        'receipts_description': 'Kudaden Sayarwa',
        'receipts_items': 'Abubuwa',
        'receipts_quantity': 'Adadi',
        'receipts_unit_price': 'Farashin Ɗaya',
        'receipts_total': 'Jimillar',
        'receipts_subtotal': 'Ƙaramin Jimillar',
        'receipts_tax': 'Haraji',
        'receipts_discount': 'Rangwame',
        'receipts_status': 'Matsayi',
        'receipts_paid': 'An Biya',
        'receipts_pending': 'Ana Jira',
        'receipts_overdue': 'Ya Wuce Lokaci',
        'receipts_cancelled': 'An Soke',
        'receipts_void': 'An Soke',
        'receipts_print': 'Buga Rasitin Sayarwa',
        'receipts_email': 'Aika Rasitin Sayarwa ta Imel',
        'receipts_duplicate': 'Kwafi Sayarwa',
        'receipts_refund': 'Mayar da Kuɗi',
        'receipts_notes': 'Bayanai',
        'receipts_terms': 'Sharuɗa da Yanayi',
        'receipts_signature': 'Sa Hannu',
        'receipts_company_info': 'Bayanan Kamfani',
        'receipts_receipt_created': 'An rubuta sayarwa cikin nasara',
        'receipts_receipt_updated': 'An sabunta sayarwa cikin nasara',
        'receipts_receipt_deleted': 'An goge sayarwa cikin nasara',
        'receipts_confirm_delete': 'Ka tabbata kana son goge wannan sayarwa?',
        'receipts_no_receipts': 'Ba a sami kudaden sayarwa ba',
        'receipts_tooltip': 'Duba da sarrafa kudaden sayarwa',
        'receipts_search_receipts': 'Nemo sayarwa...',
        'receipts_total_receipts': 'Jimillar Sayarwa',
        'receipts_total_amount': 'Jimillar Kudaden Sayarwa',
        'receipts_insufficient_coins': 'Ba isassun kuɗaɗe don rubuta sayarwa',
        'receipts_add_money_in': 'Rubuta Kudaden Sayarwa',
        'receipts_money_in': 'Kudaden Sayarwa',
        'receipts_money_in_subtext': 'Bi diddigin kudaden sayarwa',
        'receipts_no_money_in': 'Babu kudaden sayarwa da aka rubuta',
        'receipts_today_receipts': 'Sayarwar Yau',
        'receipts_monthly_receipts': 'Sayarwar Wata',
        # Receipts
        'receipts_payer_name': 'Sunan Abokin Ciniki',
    }
}

class ReceiptForm(FlaskForm):
    party_name = StringField(trans('receipts_payer_name', default='Payer Name'), validators=[DataRequired()])
    date = DateField(trans('general_date', default='Date'), validators=[DataRequired()])
    amount = FloatField(trans('receipts_amount', default='Amount'), validators=[DataRequired()])
    method = SelectField(trans('general_payment_method', default='Payment Method'), choices=[
        ('cash', trans('general_cash', default='Cash')),
        ('card', trans('general_card', default='Card')),
        ('bank', trans('general_bank_transfer', default='Bank Transfer'))
    ], validators=[Optional()])
    category = StringField(trans('general_category', default='Category'), validators=[Optional()])
    submit = SubmitField(trans('receipts_add_receipt', default='Add Receipt'))

receipts_bp = Blueprint('receipts', __name__, url_prefix='/receipts')

@receipts_bp.route('/')
@login_required
@utils.requires_role('trader')
def index():
    """List all receipt cashflows for the current user."""
    try:
        db = utils.get_mongo_db()
        query = {'type': 'receipt'} if utils.is_admin() else {'user_id': str(current_user.id), 'type': 'receipt'}
        receipts = list(db.cashflows.find(query).sort('created_at', -1))
        return render_template(
            'receipts/index.html',
            receipts=receipts,
            format_currency=utils.format_currency,
            format_date=utils.format_date,
            title=trans('receipts_title', default='Receipts', lang=session.get('lang', 'en'))
        )
    except Exception as e:
        logger.error(f"Error fetching receipts for user {current_user.id}: {str(e)}")
        flash(trans('receipts_fetch_error', default='An error occurred'), 'danger')
        return redirect(url_for('index'))

@receipts_bp.route('/view/<id>')
@login_required
@utils.requires_role('trader')
def view(id):
    """View detailed information about a specific receipt."""
    try:
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        receipt = db.cashflows.find_one(query)
        if not receipt:
            return jsonify({'error': trans('receipts_record_not_found', default='Record not found')}), 404
        receipt['_id'] = str(receipt['_id'])
        receipt['created_at'] = receipt['created_at'].isoformat() if receipt.get('created_at') else None
        return jsonify(receipt)
    except Exception as e:
        logger.error(f"Error fetching receipt {id} for user {current_user.id}: {str(e)}")
        return jsonify({'error': trans('receipts_fetch_error', default='An error occurred')}), 500

@receipts_bp.route('/generate_pdf/<id>')
@login_required
@utils.requires_role('trader')
def generate_pdf(id):
    """Generate PDF receipt for a receipt transaction."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        receipt = db.cashflows.find_one(query)
        if not receipt:
            flash(trans('receipts_record_not_found', default='Record not found'), 'danger')
            return redirect(url_for('index'))
        if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
            flash(trans('debtors_insufficient_credits', default='Insufficient credits to generate receipt'), 'danger')
            return redirect(url_for('credits.request_credits'))
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        p.setFont("Helvetica-Bold", 24)
        p.drawString(inch, height - inch, "FiCore Records - Money In Receipt")
        p.setFont("Helvetica", 12)
        y_position = height - inch - 0.5 * inch
        p.drawString(inch, y_position, f"Payer: {receipt['party_name']}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Amount Received: {utils.format_currency(receipt['amount'])}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Payment Method: {receipt.get('method', 'N/A')}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Category: {receipt.get('category', 'No category provided')}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Date: {utils.format_date(receipt['created_at'])}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Receipt ID: {str(receipt['_id'])}")
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(inch, inch, "This document serves as an official receipt generated by FiCore Records.")
        p.showPage()
        p.save()
        if not utils.is_admin():
            user_query = utils.get_user_query(str(current_user.id))
            db.users.update_one(user_query, {'$inc': {'ficore_credit_balance': -1}})
            db.credit_transactions.insert_one({
                'user_id': str(current_user.id),
                'amount': -1,
                'type': 'spend',
                'date': datetime.utcnow(),
                'ref': f"Receipt PDF generated for {receipt['party_name']} (Ficore Credits)"
            })
        buffer.seek(0)
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=receipt_{receipt["party_name"]}_{str(receipt["_id"])}.pdf'
            }
        )
    except Exception as e:
        logger.error(f"Error generating PDF for receipt {id}: {str(e)}")
        flash(trans('receipts_pdf_generation_error', default='An error occurred'), 'danger')
        return redirect(url_for('index'))

@receipts_bp.route('/add', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def add():
    """Add a new receipt cashflow."""
    form = ReceiptForm()
    if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
        flash(trans('debtors_insufficient_credits', default='Insufficient credits to add a receipt. Request more credits.'), 'danger')
        return redirect(url_for('credits.request_credits'))
    if form.validate_on_submit():
        try:
            db = utils.get_mongo_db()
            receipt_date = datetime(form.date.data.year, form.date.data.month, form.date.data.day)
            cashflow = {
                'user_id': str(current_user.id),
                'type': 'receipt',
                'party_name': form.party_name.data,
                'amount': form.amount.data,
                'method': form.method.data,
                'category': form.category.data,
                'created_at': receipt_date,
                'updated_at': datetime.utcnow()
            }
            db.cashflows.insert_one(cashflow)
            if not utils.is_admin():
                user_query = utils.get_user_query(str(current_user.id))
                db.users.update_one(user_query, {'$inc': {'ficore_credit_balance': -1}})
                db.credit_transactions.insert_one({
                    'user_id': str(current_user.id),
                    'amount': -1,
                    'type': 'spend',
                    'date': datetime.utcnow(),
                    'ref': f"Receipt creation: {cashflow['party_name']} (Ficore Credits)"
                })
            flash(trans('receipts_add_success', default='Receipt added successfully'), 'success')
            return redirect(url_for('receipts.index'))
        except Exception as e:
            logger.error(f"Error adding receipt for user {current_user.id}: {str(e)}")
            flash(trans('receipts_add_error', default='An error occurred'), 'danger')
    return render_template(
        'receipts/add.html',
        form=form,
        title=trans('receipts_add_title', default='Add Receipt', lang=session.get('lang', 'en'))
    )

@receipts_bp.route('/edit/<id>', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def edit(id):
    """Edit an existing receipt cashflow."""
    try:
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        receipt = db.cashflows.find_one(query)
        if not receipt:
            flash(trans('receipts_record_not_found', default='Cashflow not found'), 'danger')
            return redirect(url_for('index'))
        form = ReceiptForm(data={
            'party_name': receipt['party_name'],
            'date': receipt['created_at'],
            'amount': receipt['amount'],
            'method': receipt.get('method'),
            'category': receipt.get('category')
        })
        if form.validate_on_submit():
            try:
                receipt_date = datetime(form.date.data.year, form.date.data.month, form.date.data.day)
                updated_cashflow = {
                    'party_name': form.party_name.data,
                    'amount': form.amount.data,
                    'method': form.method.data,
                    'category': form.category.data,
                    'created_at': receipt_date,
                    'updated_at': datetime.utcnow()
                }
                db.cashflows.update_one({'_id': ObjectId(id)}, {'$set': updated_cashflow})
                flash(trans('receipts_edit_success', default='Receipt updated successfully'), 'success')
                return redirect(url_for('receipts.index'))
            except Exception as e:
                logger.error(f"Error updating receipt {id} for user {current_user.id}: {str(e)}")
                flash(trans('receipts_edit_error', default='An error occurred'), 'danger')
        return render_template(
            'receipts/edit.html',
            form=form,
            receipt=receipt,
            title=trans('receipts_edit_title', default='Edit Receipt', lang=session.get('lang', 'en'))
        )
    except Exception as e:
        logger.error(f"Error fetching receipt {id} for user {current_user.id}: {str(e)}")
        flash(trans('receipts_record_not_found', default='Cashflow not found'), 'danger')
        return redirect(url_for('index'))

@receipts_bp.route('/delete/<id>', methods=['POST'])
@login_required
@utils.requires_role('trader')
def delete(id):
    """Delete a receipt cashflow."""
    try:
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        result = db.cashflows.delete_one(query)
        if result.deleted_count:
            flash(trans('receipts_delete_success', default='Receipt deleted successfully'), 'success')
        else:
            flash(trans('receipts_record_not_found', default='Cashflow not found'), 'danger')
        return redirect(url_for('receipts.index'))
    except Exception as e:
        logger.error(f"Error deleting receipt {id} for user {current_user.id}: {str(e)}")
        flash(trans('receipts_delete_error', default='An error occurred'), 'danger')
        return redirect(url_for('index'))