"""Add marketplace listings, orders and eSewa payment records.

Revision ID: d4e5f6a7b8c9
Revises: bc5c6503d712
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'bc5c6503d712'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prediction_id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('buyer_id', sa.Integer(), nullable=True),
        sa.Column('price', sa.Numeric(14, 2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('condition_notes', sa.Text(), nullable=True),
        sa.Column('location', sa.String(120), nullable=False),
        sa.Column('contact_phone', sa.String(30), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('sold_at', sa.DateTime(), nullable=True),
        sa.Column('reserved_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE', 'RESERVED', 'SOLD', 'REMOVED')", name='ck_listings_status'),
        sa.ForeignKeyConstraint(['prediction_id'], ['estimates.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prediction_id'),
    )
    op.create_index('ix_listings_status', 'listings', ['status'])
    op.create_index('ix_listings_seller_id', 'listings', ['seller_id'])
    op.create_index('ix_listings_buyer_id', 'listings', ['buyer_id'])
    op.create_index('ix_listings_created_at', 'listings', ['created_at'])
    op.create_table(
        'listing_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(255), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_listing_images_listing_id', 'listing_images', ['listing_id'])
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('buyer_id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('transaction_uuid', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('seller_payment_status', sa.String(20), nullable=False),
        sa.CheckConstraint("status IN ('PENDING_PAYMENT', 'PAID', 'FAILED', 'CANCELLED', 'REFUNDED')", name='ck_orders_status'),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_uuid'),
    )
    op.create_index('ix_orders_listing_id', 'orders', ['listing_id'])
    op.create_index('ix_orders_buyer_id', 'orders', ['buyer_id'])
    op.create_index('ix_orders_seller_id', 'orders', ['seller_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('transaction_uuid', sa.String(64), nullable=False),
        sa.Column('provider_transaction_code', sa.String(100), nullable=True),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
        sa.UniqueConstraint('transaction_uuid'),
    )
    op.create_index('ix_payments_status', 'payments', ['status'])


def downgrade():
    op.drop_table('payments')
    op.drop_table('orders')
    op.drop_table('listing_images')
    op.drop_table('listings')
