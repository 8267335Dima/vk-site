"""Initial migration

Revision ID: f7159ac9ff98
Revises: 
Create Date: 2025-09-11 21:28:17.470043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7159ac9ff98'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### КОД НИЖЕ ПОЛНОСТЬЮ ИСПРАВЛЕН ###

    # Шаг 1: Создаем таблицу 'users', от которой зависят все остальные
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vk_id', sa.BigInteger(), nullable=False),
        sa.Column('encrypted_vk_token', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('plan', sa.String(), server_default='Базовый', nullable=False),
        sa.Column('plan_expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('daily_likes_limit', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('daily_add_friends_limit', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('delay_profile', sa.Enum('slow', 'normal', 'fast', name='delayprofile'), server_default='normal', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_vk_id'), 'users', ['vk_id'], unique=True)

    # Шаг 2: Создаем все остальные таблицы, которые ссылаются на 'users'
    op.create_table('action_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_action_logs_action_type'), 'action_logs', ['action_type'], unique=False)
    op.create_index(op.f('ix_action_logs_timestamp'), 'action_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_action_logs_user_id'), 'action_logs', ['user_id'], unique=False)

    op.create_table('automations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('automation_type', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'automation_type', name='_user_automation_uc')
    )
    op.create_index(op.f('ix_automations_automation_type'), 'automations', ['automation_type'], unique=False)
    op.create_index(op.f('ix_automations_user_id'), 'automations', ['user_id'], unique=False)

    op.create_table('daily_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('likes_count', sa.Integer(), nullable=False),
        sa.Column('like_friends_feed_count', sa.Integer(), nullable=False),
        sa.Column('friends_added_count', sa.Integer(), nullable=False),
        sa.Column('friend_requests_accepted_count', sa.Integer(), nullable=False),
        sa.Column('stories_viewed_count', sa.Integer(), nullable=False),
        sa.Column('friends_removed_count', sa.Integer(), nullable=False),
        sa.Column('messages_sent_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='_user_date_uc')
    )
    op.create_index('ix_daily_stats_user_date', 'daily_stats', ['user_id', 'date'], unique=False)

    op.create_table('friends_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('friends_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='_user_date_friends_uc')
    )
    op.create_index('ix_friends_history_user_date', 'friends_history', ['user_id', 'date'], unique=False)

    op.create_table('login_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_history_timestamp'), 'login_history', ['timestamp'], unique=False)
    op.create_index(op.f('ix_login_history_user_id'), 'login_history', ['user_id'], unique=False)
    
    op.create_table('monthly_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('month_identifier', sa.String(), nullable=False),
        sa.Column('likes_count', sa.Integer(), nullable=False),
        sa.Column('friends_added_count', sa.Integer(), nullable=False),
        sa.Column('friend_requests_accepted_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'month_identifier', name='_user_month_uc')
    )

    op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('level', sa.String(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    op.create_table('payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_system_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('plan_name', sa.String(), nullable=False),
        sa.Column('months', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_payment_system_id'), 'payments', ['payment_system_id'], unique=True)
    op.create_index(op.f('ix_payments_user_id'), 'payments', ['user_id'], unique=False)

    op.create_table('profile_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('total_likes_on_content', sa.Integer(), nullable=False),
        sa.Column('friends_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='_user_date_metric_uc')
    )
    op.create_index('ix_profile_metrics_user_date', 'profile_metrics', ['user_id', 'date'], unique=False)

    op.create_table('proxies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('encrypted_proxy_url', sa.String(), nullable=False),
        sa.Column('is_working', sa.Boolean(), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('check_status_message', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'encrypted_proxy_url', name='_user_proxy_uc')
    )
    op.create_index(op.f('ix_proxies_is_working'), 'proxies', ['is_working'], unique=False)
    op.create_index(op.f('ix_proxies_user_id'), 'proxies', ['user_id'], unique=False)

    op.create_table('scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('schedule', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scenarios_user_id'), 'scenarios', ['user_id'], unique=False)

    op.create_table('sent_congratulations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('friend_vk_id', sa.BigInteger(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'friend_vk_id', 'year', name='_user_friend_year_uc')
    )
    op.create_index(op.f('ix_sent_congratulations_friend_vk_id'), 'sent_congratulations', ['friend_vk_id'], unique=False)
    op.create_index(op.f('ix_sent_congratulations_user_id'), 'sent_congratulations', ['user_id'], unique=False)

    op.create_table('task_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('celery_task_id', sa.String(), nullable=True),
        sa.Column('task_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_history_celery_task_id'), 'task_history', ['celery_task_id'], unique=True)
    op.create_index(op.f('ix_task_history_status'), 'task_history', ['status'], unique=False)
    op.create_index(op.f('ix_task_history_task_name'), 'task_history', ['task_name'], unique=False)
    op.create_index(op.f('ix_task_history_user_id'), 'task_history', ['user_id'], unique=False)
    op.create_index('ix_task_history_user_status', 'task_history', ['user_id', 'status'], unique=False)

    op.create_table('weekly_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_identifier', sa.String(), nullable=False),
        sa.Column('likes_count', sa.Integer(), nullable=False),
        sa.Column('friends_added_count', sa.Integer(), nullable=False),
        sa.Column('friend_requests_accepted_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'week_identifier', name='_user_week_uc')
    )

    # Шаг 3: Создаем таблицы, которые ссылаются на другие (не 'users')
    op.create_table('scenario_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scenario_steps_scenario_id'), 'scenario_steps', ['scenario_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### КОД НИЖЕ ПОЛНОСТЬЮ ИСПРАВЛЕН ###
    # Удаляем таблицы в обратном порядке создания
    op.drop_index(op.f('ix_scenario_steps_scenario_id'), table_name='scenario_steps')
    op.drop_table('scenario_steps')
    
    op.drop_table('weekly_stats')

    op.drop_index('ix_task_history_user_status', table_name='task_history')
    op.drop_index(op.f('ix_task_history_user_id'), table_name='task_history')
    op.drop_index(op.f('ix_task_history_task_name'), table_name='task_history')
    op.drop_index(op.f('ix_task_history_status'), table_name='task_history')
    op.drop_index(op.f('ix_task_history_celery_task_id'), table_name='task_history')
    op.drop_table('task_history')

    op.drop_index(op.f('ix_sent_congratulations_user_id'), table_name='sent_congratulations')
    op.drop_index(op.f('ix_sent_congratulations_friend_vk_id'), table_name='sent_congratulations')
    op.drop_table('sent_congratulations')

    op.drop_index(op.f('ix_scenarios_user_id'), table_name='scenarios')
    op.drop_table('scenarios')

    op.drop_index(op.f('ix_proxies_user_id'), table_name='proxies')
    op.drop_index(op.f('ix_proxies_is_working'), table_name='proxies')
    op.drop_table('proxies')

    op.drop_index('ix_profile_metrics_user_date', table_name='profile_metrics')
    op.drop_table('profile_metrics')

    op.drop_index(op.f('ix_payments_user_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_payment_system_id'), table_name='payments')
    op.drop_table('payments')

    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')

    op.drop_table('monthly_stats')

    op.drop_index(op.f('ix_login_history_user_id'), table_name='login_history')
    op.drop_index(op.f('ix_login_history_timestamp'), table_name='login_history')
    op.drop_table('login_history')

    op.drop_index('ix_friends_history_user_date', table_name='friends_history')
    op.drop_table('friends_history')
    
    op.drop_index('ix_daily_stats_user_date', table_name='daily_stats')
    op.drop_table('daily_stats')

    op.drop_index(op.f('ix_automations_user_id'), table_name='automations')
    op.drop_index(op.f('ix_automations_automation_type'), table_name='automations')
    op.drop_table('automations')

    op.drop_index(op.f('ix_action_logs_user_id'), table_name='action_logs')
    op.drop_index(op.f('ix_action_logs_timestamp'), table_name='action_logs')
    op.drop_index(op.f('ix_action_logs_action_type'), table_name='action_logs')
    op.drop_table('action_logs')

    op.drop_index(op.f('ix_users_vk_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###