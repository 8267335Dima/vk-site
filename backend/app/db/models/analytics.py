# --- START OF FILE backend/app/db/models/analytics.py ---

import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, JSON, Index, Date, Enum, text
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.enums import FriendRequestStatus

class DailyStats(Base):
    __tablename__ = "daily_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    stories_viewed_count = Column(Integer, default=0, nullable=False)
    friends_removed_count = Column(Integer, default=0, nullable=False)
    messages_sent_count = Column(Integer, default=0, nullable=False)
    posts_created_count = Column(Integer, nullable=False, server_default=text('0'))
    groups_joined_count = Column(Integer, nullable=False, server_default=text('0'))
    groups_left_count = Column(Integer, nullable=False, server_default=text('0'))
    user = relationship("User", back_populates="daily_stats")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_uc'),
        Index('ix_daily_stats_user_date', 'user_id', 'date'),
    )

class WeeklyStats(Base):
    __tablename__ = "weekly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_identifier = Column(String, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    user = relationship("User")
    __table_args__ = (UniqueConstraint('user_id', 'week_identifier', name='_user_week_uc'),)

class MonthlyStats(Base):
    __tablename__ = "monthly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month_identifier = Column(String, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    user = relationship("User")
    __table_args__ = (UniqueConstraint('user_id', 'month_identifier', name='_user_month_uc'),)

class ProfileMetric(Base):
    __tablename__ = "profile_metrics"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    
    friends_count = Column(Integer, nullable=False, default=0)
    followers_count = Column(Integer, nullable=False, default=0)
    photos_count = Column(Integer, nullable=False, default=0)
    wall_posts_count = Column(Integer, nullable=False, default=0)
    
    # <<< ИЗМЕНЕНО: Поля для лайков разделены >>>
    recent_post_likes = Column(Integer, nullable=False, default=0)
    recent_photo_likes = Column(Integer, nullable=False, default=0)
    total_post_likes = Column(Integer, nullable=False, default=0)
    total_photo_likes = Column(Integer, nullable=False, default=0)
    
    user = relationship("User", back_populates="profile_metrics")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_metric_uc'),
        Index('ix_profile_metrics_user_date', 'user_id', 'date'),
    )

class FriendsHistory(Base):
    __tablename__ = "friends_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    friends_count = Column(Integer, nullable=False)
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_friends_uc'),
        Index('ix_friends_history_user_date', 'user_id', 'date'),
    )

class PostActivityHeatmap(Base):
    __tablename__ = "post_activity_heatmaps"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    heatmap_data = Column(JSON, nullable=False)
    last_updated_at = Column(DateTime(timezone=True), default=datetime.datetime.now(datetime.UTC), onupdate=datetime.datetime.now(datetime.UTC))
    user = relationship("User", back_populates="heatmap")

class FriendRequestLog(Base):
    __tablename__ = "friend_request_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_vk_id = Column(BigInteger, nullable=False, index=True)
    status = Column(Enum(FriendRequestStatus), nullable=False, default=FriendRequestStatus.pending, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now(datetime.UTC), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="friend_requests")
    __table_args__ = (UniqueConstraint('user_id', 'target_vk_id', name='_user_target_uc'),)

