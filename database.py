from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

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
    status = Column(String, default='open')
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
    def __init__(self, db_url=None):
        if db_url is None:
            db_path = os.path.join(os.path.dirname(__file__), 'hostile_rust.db')
            db_url = f'sqlite:///{db_path}'
        
        self.db_path = db_url
        self.engine = create_engine(db_url, connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        print(f"✅ База данных: {db_url}")
    
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
                print(f"✅ Новый пользователь: {first_name} {last_name} (ID: {vk_id})")
            return user
        except Exception as e:
            print(f"❌ Ошибка add_user: {e}")
            session.rollback()
            return None
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
            existing = session.query(PromoCode).filter_by(code=code).first()
            if existing:
                print(f"⚠️ Промокод {code} уже существует")
                return existing
            
            promo = PromoCode(code=code, description=description)
            session.add(promo)
            session.commit()
            print(f"✅ Добавлен промокод: {code}")
            return promo
        except Exception as e:
            print(f"❌ Ошибка add_promo: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def delete_promo(self, code):
        session = self.get_session()
        try:
            promo = session.query(PromoCode).filter_by(code=code).first()
            if promo:
                session.delete(promo)
                session.commit()
                print(f"✅ Удален промокод: {code}")
                return True
            return False
        except Exception as e:
            print(f"❌ Ошибка delete_promo: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_active_promos(self):
        session = self.get_session()
        try:
            return session.query(PromoCode).filter_by(is_active=True).all()
        finally:
            session.close()
    
    def record_promo_usage(self, user_id, promo_code):
        """Запись использования промокода (только для истории, без активации в игре)"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(vk_id=user_id).first()
            promo = session.query(PromoCode).filter_by(code=promo_code, is_active=True).first()
            
            if not user or not promo:
                return False, "Пользователь или промокод не найден"
            
            # Проверяем, использовал ли уже пользователь этот промокод
            used = session.query(PromoUsage).filter_by(
                user_id=user.id, promo_id=promo.id
            ).first()
            
            if used:
                return False, "Вы уже запрашивали этот промокод"
            
            usage = PromoUsage(user_id=user.id, promo_id=promo.id)
            session.add(usage)
            session.commit()
            return True, "Промокод сохранен в историю"
        except Exception as e:
            print(f"❌ Ошибка record_promo_usage: {e}")
            session.rollback()
            return False, "Ошибка записи"
        finally:
            session.close()
    
    def get_last_promo_user(self, promo_code):
        """Получить последнего пользователя, получившего промокод"""
        session = self.get_session()
        try:
            promo = session.query(PromoCode).filter_by(code=promo_code).first()
            if not promo:
                return None
            
            usage = session.query(PromoUsage).filter_by(promo_id=promo.id).order_by(PromoUsage.used_at.desc()).first()
            if usage:
                return usage.user, usage.used_at
            return None
        except Exception as e:
            print(f"❌ Ошибка get_last_promo_user: {e}")
            return None
        finally:
            session.close()
    
    def get_all_promo_usage(self):
        """Получить всю историю использования промокодов"""
        session = self.get_session()
        try:
            return session.query(PromoUsage).order_by(PromoUsage.used_at.desc()).all()
        finally:
            session.close()
    
    def create_ticket(self, vk_id, title):
        session = self.get_session()
        try:
            user = session.query(User).filter_by(vk_id=vk_id).first()
            if not user:
                user = User(vk_id=vk_id, first_name="Unknown", last_name="User")
                session.add(user)
                session.commit()
            
            ticket = Ticket(user_id=user.id, title=title)
            session.add(ticket)
            session.commit()
            print(f"✅ Создан тикет #{ticket.id}")
            return ticket.id
        except Exception as e:
            print(f"❌ Ошибка create_ticket: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def add_ticket_message(self, ticket_id, user_id, message, is_admin=False):
        session = self.get_session()
        try:
            msg = TicketMessage(ticket_id=ticket_id, user_id=user_id, message=message, is_admin=is_admin)
            session.add(msg)
            session.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка add_ticket_message: {e}")
            session.rollback()
            return False
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
                tickets = session.query(Ticket).filter_by(user_id=user.id).order_by(Ticket.created_at.desc()).all()
                for ticket in tickets:
                    _ = ticket.messages
                return tickets
            return []
        finally:
            session.close()
    
    def get_open_tickets(self):
        session = self.get_session()
        try:
            tickets = session.query(Ticket).filter_by(status='open').all()
            for ticket in tickets:
                _ = ticket.user
                _ = ticket.messages
            return tickets
        finally:
            session.close()
    
    def get_ticket_messages(self, ticket_id):
        session = self.get_session()
        try:
            return session.query(TicketMessage).filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
        finally:
            session.close()
