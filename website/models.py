from . import db
from sqlalchemy import Numeric
from flask_login import UserMixin
import secrets
import string

from .time import TimeByMinsk

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(), unique=True)
    last_name = db.Column(db.String())
    first_name = db.Column(db.String())
    patronymic_name = db.Column(db.String())
    post = db.Column(db.String())
    phone = db.Column(db.String(), unique=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministries.id'))
    region_id = db.Column(db.Integer, db.ForeignKey('regions.id'))
    password = db.Column(db.String())
    is_admin = db.Column(db.Boolean, default=False)
    is_auditor = db.Column(db.Boolean, default=False)
    last_active = db.Column(db.DateTime, nullable=False, default=TimeByMinsk())
    begin_time = db.Column(db.DateTime, nullable=False, default=TimeByMinsk())
    reset_password_token = db.Column(db.String(255), nullable=True)
    reset_password_expires = db.Column(db.DateTime, nullable=True)
    organization = db.relationship('Organization',
                                  foreign_keys=[organization_id],
                                  backref='users')
    ministry = db.relationship('Ministry',
                              foreign_keys=[ministry_id],
                              backref='users')
    region = db.relationship('Region',
                            foreign_keys=[region_id],
                            backref='users')
    plans = db.relationship('Plan', backref='user', lazy=True, cascade="all, delete-orphan")
    tickets = db.relationship('Ticket', back_populates='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")
    created_chats = db.relationship('Chat',
                                   back_populates='created_by',
                                   cascade='all, delete-orphan')
    def __repr__(self):
        return f'<User {self.email}>'

class Region(db.Model):
    __tablename__ = 'regions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    plans = db.relationship("Plan",
                           foreign_keys="Plan.region_id",
                           back_populates="region")

class Ministry(db.Model):
    __tablename__ = 'ministries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    organizations = db.relationship("Organization", back_populates="ministry")
    plans = db.relationship("Plan",
                           foreign_keys="Plan.ministry_id",
                           back_populates="ministry")

class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), nullable=False)
    okpo = db.Column(db.String, unique=True, nullable=False)
    ynp = db.Column(db.String(), nullable=True)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministries.id'))
    is_active = db.Column(db.Boolean, default=True)
    ministry = db.relationship("Ministry", back_populates="organizations")
    plans = db.relationship("Plan",
                           foreign_keys="Plan.org_id",
                           back_populates="organization")

def generate_static_token(length=20):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        default=lambda: generate_static_token(),
        index=True
    )
    year = db.Column(db.Integer, nullable=False)
    begin_time = db.Column(db.DateTime, nullable=False, default=TimeByMinsk())
    change_time = db.Column(db.DateTime, nullable=False, default=TimeByMinsk())
    sent_time = db.Column(db.DateTime)
    audit_time = db.Column(db.DateTime)
    energy_saving = db.Column(Numeric(scale=2))
    share_fuel = db.Column(Numeric(scale=2))
    saving_fuel = db.Column(Numeric(scale=2))
    share_energy = db.Column(Numeric(scale=2))
    is_draft = db.Column(db.Boolean, default=True)
    is_control = db.Column(db.Boolean, default=False)
    is_sent = db.Column(db.Boolean, default=False)
    is_error = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    plan_type = db.Column(db.String(50), nullable=True)  # 'org_small', 'org_large', 'ministry', 'region'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministries.id'))
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    region_id = db.Column(db.Integer, db.ForeignKey('regions.id'))
    afch = db.Column(db.Boolean, default=False)
    
    tickets = db.relationship('Ticket', back_populates='plan', lazy=True, cascade="all, delete-orphan")
    
    events = db.relationship('Event', back_populates='plan', lazy=True, cascade="all, delete-orphan")
    indicators_usage = db.relationship('IndicatorUsage', back_populates='plan', lazy=True, cascade="all, delete-orphan")
    
    ministry = db.relationship("Ministry",
                              foreign_keys=[ministry_id],
                              back_populates="plans")
    organization = db.relationship("Organization",
                                  foreign_keys=[org_id],
                                  back_populates="plans")
    region = db.relationship("Region",
                            foreign_keys=[region_id],
                            back_populates="plans")

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    begin_time = db.Column(db.DateTime, default=TimeByMinsk())
    luck = db.Column(db.Boolean, default=False)
    is_owner = db.Column(db.Boolean, default=False)
    note = db.Column(db.String(500), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    plan = db.relationship("Plan", back_populates="tickets")
    user = db.relationship("User", back_populates="tickets")

class Unit(db.Model):
    __tablename__ = 'units'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(400), unique=True, nullable=False)

class Direction(db.Model):
    __tablename__ = 'directions'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(400))
    name = db.Column(db.String(400))
    id_unit = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    
    DateStart = db.Column(db.DateTime, default=TimeByMinsk())
    DateEnd = db.Column(db.DateTime)
    
    is_econom = db.Column(db.Boolean)
    is_increase = db.Column(db.Boolean)
    
    unit = db.relationship('Unit', backref='directions', foreign_keys=[id_unit])

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    id_direction = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=False)
    id_plan = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    name = db.Column(db.String(4000), nullable=False)
    Volume = db.Column(db.Integer)
    EffTut = db.Column(Numeric(scale=2))
    EffRub = db.Column(Numeric(scale=2))
    ExpectedQuarter = db.Column(db.Integer)
    EffCurrYear = db.Column(Numeric(scale=2))
    Payback = db.Column(Numeric(scale=2))
    VolumeFin = db.Column(Numeric(scale=2))
    BudgetState = db.Column(Numeric(scale=2))
    BudgetRep = db.Column(Numeric(scale=2))
    BudgetLoc = db.Column(Numeric(scale=2))
    BudgetOther = db.Column(Numeric(scale=2))
    MoneyOwn = db.Column(Numeric(scale=2))
    MoneyLoan = db.Column(Numeric(scale=2))
    MoneyOther = db.Column(Numeric(scale=2))
    is_local = db.Column(db.Boolean)
    is_corrected = db.Column(db.Boolean)
    order = db.Column(db.Integer, default=None)
    plan = db.relationship("Plan", back_populates="events")
    direction = db.relationship('Direction', backref='events', foreign_keys=[id_direction])
    # econ_measures = db.relationship("EconMeasure", back_populates="econ_execes")

    def as_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'Volume': self.Volume,
            'EffTut': self.EffTut,
            'EffRub': self.EffRub,
            'ExpectedQuarter': self.ExpectedQuarter,
            'EffCurrYear': self.EffCurrYear,
            'Payback': self.Payback,
            'VolumeFin': self.VolumeFin,
            'BudgetState': self.BudgetState,
            'BudgetRep': self.BudgetRep,
            'BudgetLoc': self.BudgetLoc,
            'BudgetOther': self.BudgetOther,
            'MoneyOwn': self.MoneyOwn,
            'MoneyLoan': self.MoneyLoan,
            'MoneyOther': self.MoneyOther
        }

class Indicator(db.Model):
    __tablename__ = 'indicators'
    id = db.Column(db.Integer, primary_key=True)
    id_unit = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    code = db.Column(db.String(400))
    name = db.Column(db.String(400))
    CoeffToTut = db.Column(Numeric(scale=2))
    IsMandatory = db.Column(db.Boolean)
    Group = db.Column(db.Float)
    RowN = db.Column(db.Integer)
    # IsSummary = db.Column(db.Boolean)
    # IsSendRealUnit = db.Column(db.Boolean)
    # IsSelfProd = db.Column(db.Boolean)
    # IsLocal = db.Column(db.Boolean)
    # IsRenewable = db.Column(db.Boolean)
    # id_indicator_parent = db.Column(db.Integer)
    DateStart = db.Column(db.DateTime, default=None)
    DateEnd = db.Column(db.DateTime, default=None)
    unit = db.relationship('Unit', backref='indicators')
    indicators_usage = db.relationship("IndicatorUsage", back_populates="indicator")

class IndicatorUsage(db.Model):
    __tablename__ = 'indicators_usage'
    id = db.Column(db.Integer, primary_key=True)
    id_indicator = db.Column(db.Integer, db.ForeignKey('indicators.id'), nullable=False)
    id_plan = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    QYearBeforePrev = db.Column(Numeric(scale=2))
    QYearPrev = db.Column(Numeric(scale=2))
    QYearCurrent = db.Column(Numeric(scale=2))
    indicator = db.relationship("Indicator", back_populates="indicators_usage")
    plan = db.relationship("Plan", back_populates="indicators_usage")

    def as_dict(self):
        return {
            'id': self.id,
            'id_indicator': self.id_indicator,
            'id_plan': self.id_plan,
            'QYearBeforePrev': self.QYearBeforePrev,
            'QYearPrev': self.QYearPrev,
            'QYearCurrent': self.QYearCurrent,
            'CoeffToTut': self.indicator.CoeffToTut,
            'name': self.indicator.name
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)
    message = db.Column(db.String(140), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=TimeByMinsk())

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    is_user = db.Column(db.Boolean, nullable=False, default=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=TimeByMinsk())
    chat = db.relationship('Chat', foreign_keys=[chat_id], back_populates='messages')
    def __repr__(self):
        return f'<Message {self.id} in chat {self.chat_id}>'

class Chat(db.Model):
    __tablename__ = 'chats'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by = db.relationship('User', foreign_keys=[created_by_id], back_populates='created_chats')
    messages = db.relationship('ChatMessage',
                              back_populates='chat',
                              cascade='all, delete-orphan',
                              passive_deletes=True,
                              lazy='dynamic')
    created_at = db.Column(db.DateTime, nullable=False, default=TimeByMinsk())
    updated_at = db.Column(db.DateTime, nullable=False, default=TimeByMinsk(), onupdate=TimeByMinsk())
