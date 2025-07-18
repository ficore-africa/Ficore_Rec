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

class ReceiptForm(FlaskForm):
    party_name = StringField(trans('receipts_party_name', default='Customer Name'), validators=[DataRequired()])
    date = DateField(trans('general_date', default='Date'), validators=[DataRequired()])
    amount = FloatField(trans('general_amount', default='Sale Amount'), validators=[DataRequired()])
    method = SelectField(trans('general_payment_method', default='Payment Method'), choices=[
        ('cash', trans('general_cash', default='Cash')),
        ('card', trans('general_card', default='Card')),
        ('bank', trans('general_bank_transfer', default='Bank Transfer'))
    ], validators=[Optional()])
    category = StringField(trans('general_category', default='Category'), validators=[Optional()])
    submit = SubmitField(trans('receipts_add_receipt', default='Record Sale'))

receipts_bp = Blueprint('receipts', __name__, url_prefix='/receipts')

@receipts_bp.route('/')
@login_required
@utils.requires_role('trader')
def index():
    """List all sales income cashflows for the current user."""
    try:
        db = utils.get_mongo_db()
        query = {'type': 'receipt'} if utils.is_admin() else {'user_id': str(current_user.id), 'type': 'receipt'}
        sales = list(db.cashflows.find(query).sort('created_at', -1))
        return render_template(
            'receipts/index.html',
            receipts=sales,
            format_currency=utils.format_currency,
            format_date=utils.format_date,
            title=trans('receipts_title', default='Sales Income', lang=session.get('lang', 'en'))
        )
    except Exception as e:
        logger.error(f"Error fetching sales income for user {current_user.id}: {str(e)}")
        flash(trans('receipts_fetch_error', default='Error loading sales income'), 'danger')
        return redirect(url_for('index'))

@receipts_bp.route('/view/<id>')
@login_required
@utils.requires_role('trader')
def view(id):
    """View detailed information about a specific sale."""
    try:
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        sale = db.cashflows.find_one(query)
        if not sale:
            return jsonify({'error': trans('receipts_record_not_found', default='Sale record not found')}), 404
        sale['_id'] = str(sale['_id'])
        sale['created_at'] = sale['created_at'].isoformat() if sale.get('created_at') else None
        return jsonify(sale)
    except Exception as e:
        logger.error(f"Error fetching sale {id} for user {current_user.id}: {str(e)}")
        return jsonify({'error': trans('receipts_fetch_error', default='Error loading sale details')}), 500

@receipts_bp.route('/generate_pdf/<id>')
@login_required
@utils.requires_role('trader')
def generate_pdf(id):
    """Generate PDF receipt for a sales transaction."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        sale = db.cashflows.find_one(query)
        if not sale:
            flash(trans('receipts_record_not_found', default='Sale record not found'), 'danger')
            return redirect(url_for('index'))
        if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
            flash(trans('debtors_insufficient_credits', default='Insufficient credits to generate sales receipt'), 'danger')
            return redirect(url_for('credits.request_credits'))
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        p.setFont("Helvetica-Bold", 24)
        p.drawString(inch, height - inch, "FiCore Records - Sales Income Receipt")
        p.setFont("Helvetica", 12)
        y_position = height - inch - 0.5 * inch
        p.drawString(inch, y_position, f"Customer: {sale['party_name']}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Sale Amount: {utils.format_currency(sale['amount'])}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Payment Method: {sale.get('method', 'N/A')}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Category: {sale.get('category', 'No category provided')}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Date: {utils.format_date(sale['created_at'])}")
        y_position -= 0.3 * inch
        p.drawString(inch, y_position, f"Sale ID: {str(sale['_id'])}")
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(inch, inch, "This document serves as an official sales receipt generated by FiCore Records.")
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
                'ref': f"Sales receipt PDF generated for {sale['party_name']} (Ficore Credits)"
            })
        buffer.seek(0)
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=sales_receipt_{sale["party_name"]}_{str(sale["_id"])}.pdf'
            }
        )
    except Exception as e:
        logger.error(f"Error generating PDF for sale {id}: {str(e)}")
        flash(trans('receipts_pdf_generation_error', default='Error generating sales receipt'), 'danger')
        return redirect(url_for('index'))

@receipts_bp.route('/add', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def add():
    """Add a new sales income record."""
    form = ReceiptForm()
    if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
        flash(trans('debtors_insufficient_credits', default='Insufficient credits to record sale. Request more credits.'), 'danger')
        return redirect(url_for('credits.request_credits'))
    if form.validate_on_submit():
        try:
            db = utils.get_mongo_db()
            sale_date = datetime(form.date.data.year, form.date.data.month, form.date.data.day)
            cashflow = {
                'user_id': str(current_user.id),
                'type': 'receipt',
                'party_name': form.party_name.data,
                'amount': form.amount.data,
                'method': form.method.data,
                'category': form.category.data,
                'created_at': sale_date,
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
                    'ref': f"Sales record creation: {cashflow['party_name']} (Ficore Credits)"
                })
            flash(trans('receipts_add_success', default='Sale recorded successfully'), 'success')
            return redirect(url_for('receipts.index'))
        except Exception as e:
            logger.error(f"Error recording sale for user {current_user.id}: {str(e)}")
            flash(trans('receipts_add_error', default='Error recording sale'), 'danger')
    return render_template(
        'receipts/add.html',
        form=form,
        title=trans('receipts_add_title', default='Record Sale', lang=session.get('lang', 'en'))
    )

@receipts_bp.route('/edit/<id>', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def edit(id):
    """Edit an existing sales income record."""
    try:
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        sale = db.cashflows.find_one(query)
        if not sale:
            flash(trans('receipts_record_not_found', default='Sale record not found'), 'danger')
            return redirect(url_for('index'))
        form = ReceiptForm(data={
            'party_name': sale['party_name'],
            'date': sale['created_at'],
            'amount': sale['amount'],
            'method': sale.get('method'),
            'category': sale.get('category')
        })
        if form.validate_on_submit():
            try:
                sale_date = datetime(form.date.data.year, form.date.data.month, form.date.data.day)
                updated_cashflow = {
                    'party_name': form.party_name.data,
                    'amount': form.amount.data,
                    'method': form.method.data,
                    'category': form.category.data,
                    'created_at': sale_date,
                    'updated_at': datetime.utcnow()
                }
                db.cashflows.update_one({'_id': ObjectId(id)}, {'$set': updated_cashflow})
                flash(trans('receipts_edit_success', default='Sale updated successfully'), 'success')
                return redirect(url_for('receipts.index'))
            except Exception as e:
                logger.error(f"Error updating sale {id} for user {current_user.id}: {str(e)}")
                flash(trans('receipts_edit_error', default='Error updating sale'), 'danger')
        return render_template(
            'receipts/edit.html',
            form=form,
            receipt=sale,
            title=trans('receipts_edit_title', default='Edit Sale', lang=session.get('lang', 'en'))
        )
    except Exception as e:
        logger.error(f"Error fetching sale {id} for user {current_user.id}: {str(e)}")
        flash(trans('receipts_record_not_found', default='Sale record not found'), 'danger')
        return redirect(url_for('index'))

@receipts_bp.route('/delete/<id>', methods=['POST'])
@login_required
@utils.requires_role('trader')
def delete(id):
    """Delete a sales income record."""
    try:
        db = utils.get_mongo_db()
        query = {'_id': ObjectId(id), 'type': 'receipt'} if utils.is_admin() else {'_id': ObjectId(id), 'user_id': str(current_user.id), 'type': 'receipt'}
        result = db.cashflows.delete_one(query)
        if result.deleted_count:
            flash(trans('receipts_delete_success', default='Sale record deleted successfully'), 'success')
        else:
            flash(trans('receipts_record_not_found', default='Sale record not found'), 'danger')
        return redirect(url_for('receipts.index'))
    except Exception as e:
        logger.error(f"Error deleting sale {id} for user {current_user.id}: {str(e)}")
        flash(trans('receipts_delete_error', default='Error deleting sale record'), 'danger')
        return redirect(url_for('index'))
