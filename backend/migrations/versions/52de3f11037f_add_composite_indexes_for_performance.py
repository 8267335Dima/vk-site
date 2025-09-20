"""drop_friend_interactions_table

Revision ID: <your_new_revision_id>
Revises: <previous_revision_id_with_indexes>
Create Date: ...

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '<your_new_revision_id>'
down_revision = '<previous_revision_id_with_indexes>'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_table('friend_interactions')

def downgrade() -> None:
    op.create_table('friend_interactions',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('friend_vk_id', sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column('likes_to_friend', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('likes_from_friend', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('comments_to_friend', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('comments_from_friend', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('last_message_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('last_updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_friend_interactions_user_id_users', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_friend_interactions'),
        sa.UniqueConstraint('user_id', 'friend_vk_id', name='_user_friend_interaction_uc')
    )