from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    subscribed = Column(Boolean, default=True)
    registered_at = Column(DateTime, default=datetime.now)
    
    tickets = relationship("Ticket", back_populates="user")
    promo_uses = relationship("PromoUsage", back_populates="user")

class PromoCode(Base):
    __tablename__ = 'promocodes'
    
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    uses = Column(Integer, default=0)
    
    usage_history = relationship("PromoUsage", back_populates="promo")

class PromoUsage(Base):
    __tablename__ = 'promo_usage'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    promo_id = Column(Integer, ForeignKey('promocodes.id'))
    used_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="promo_uses")
    promo = relationship("PromoCode", back_populates="usage_history")

class Ticket(Base):
    __tablename__ = 'tickets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String)
    status = Column(String, default='open')  # open, in_progress, closed
    created_at = Column(DateTime, default=datetime.now)
    closed_at = Column(DateTime)
    
    user = relationship("User", back_populates="tickets")
    messages = relationship("TicketMessage", back_populates="ticket")

class TicketMessage(Base):
    __tablename__ = 'ticket_messages'
    
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id'))
    user_id = Column(Integer)
    message = Column(Text)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    ticket = relationship("Ticket", back_populates="messages")

class Database:
    def __init__(self, db_url='sqlite:///hostile_rust.db'):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.Session()
    
    def add_user(self, vk_id, first_name, last_name):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(vk_id=vk_id).first()
            if not user:
                user = User(vk_id=vk_id, first_name=first_name, last_name=last_name)
                session.add(user)
                session.commit()
                print(f"Новый пользователь: {first_name} {last_name} (ID: {vk_id})")
            return user
        finally:
            session.close()
    
    def get_user(self, vk_id):
        session = self.get_session()
        try:
            return session.query(User).filter_by(vk_id=vk_id).first()
        finally:
            session.close()
    
    def get_all_users(self):
        session = self.get_session()
        try:
            return session.query(User).filter_by(subscribed=True).all()
        finally:
            session.close()
    
    def add_promo(self, code, description):
        session = self.get_session()
        try:
            promo = PromoCode(code=code, description=description)
            session.add(promo)
            session.commit()
            return promo
        finally:
            session.close()
    
    def delete_promo(self, code):
        session = self.get_session()
        try:
            promo = session.query(PromoCode).filter_by(code=code).first()
            if promo:
                session.delete(promo)
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    def get_active_promos(self):
        session = self.get_session()
        try:
            return session.query(PromoCode).filter_by(is_active=True).all()
        finally:
            session.close()
    
    def use_promo(self, vk_id, promo_code):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(vk_id=vk_id).first()
            promo = session.query(PromoCode).filter_by(code=promo_code, is_active=True).first()
            
            if not user or not promo:
                return False, "Пользователь или промокод не найден"
            
            used = session.query(PromoUsage).filter_by(
                user_id=user.id, promo_id=promo.id
            ).first()
            
            if used:
                return False, "Вы уже использовали этот промокод"
            
            usage = PromoUsage(user_id=user.id, promo_id=promo.id)
            session.add(usage)
            promo.uses += 1
            session.commit()
            return True, "Промокод успешно активирован"
        finally:
            session.close()
    
    def create_ticket(self, vk_id, title):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                ticket = Ticket(user_id=user.id, title=title)
                session.add(ticket)
                session.commit()
                return ticket.id
            return None
        finally:
            session.close()
    
    def add_ticket_message(self, ticket_id, user_id, message, is_admin=False):
        session = self.get_session()
        try:
            msg = TicketMessage(
                ticket_id=ticket_id,
                user_id=user_id,
                message=message,
                is_admin=is_admin
            )
            session.add(msg)
            session.commit()
        finally:
            session.close()
    
    def get_ticket(self, ticket_id):
        session = self.get_session()
        try:
            return session.query(Ticket).filter_by(id=ticket_id).first()
        finally:
            session.close()
    
    def close_ticket(self, ticket_id):
        session = self.get_session()
        try:
            ticket = session.query(Ticket).filter_by(id=ticket_id).first()
            if ticket and ticket.status != 'closed':
                ticket.status = 'closed'
                ticket.closed_at = datetime.now()
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    def get_user_tickets(self, vk_id):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(vk_id=vk_id).first()
            if user:
                return session.query(Ticket).filter_by(user_id=user.id).order_by(Ticket.created_at.desc()).all()
            return []
        finally:
            session.close()
    
    def get_open_tickets(self):
        session = self.get_session()
        try:
            return session.query(Ticket).filter_by(status='open').all()
        finally:
            session.close()
    
    def get_ticket_messages(self, ticket_id):
        session = self.get_session()
        try:
            return session.query(TicketMessage).filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
        finally:
            session.close()
