import bcrypt

from sqlalchemy import create_engine
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Binary
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, synonym

db_string = 'postgres://board:root1234@localhost:5432/board'

db = create_engine(db_string)
session_factory = sessionmaker(bind=db)
Session = scoped_session(session_factory)
session = Session()
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column('user_id', Integer, primary_key=True)
    email = Column('user_email', String(255))
    password = Column('user_password', Binary(60))

    items = relationship('Item', back_populates='owner')

    def __init__(self, email, password):
        self.email = email
        self.password = password

    @classmethod
    def from_json(cls, data):
        return cls(**data)

    def to_json(self):
        to_serialize = ['id', 'email']
        data = {}
        for attr_name in to_serialize:
            data[attr_name] = getattr(self, attr_name)
        return data


class Item(Base):
    __tablename__ = 'items'

    id = Column('item_id', Integer, primary_key=True)
    title = Column('item_title', String(64))
    text = Column('item_text', String(255))
    _created_at = Column('item_created', DateTime(), default=func.current_timestamp())
    created_by = Column('item_owner', Integer, ForeignKey('users.user_id'))

    owner = relationship('User', foreign_keys=[created_by], back_populates='items')
    
    def __init__(self, title, text, created_by):
        self.title = title
        self.text = text
        self.created_by = created_by

    @hybrid_property
    def created_at(self):
        return self._created_at.isoformat()

    @created_at.setter
    def created_at(self, created_at):
        self._created_at = created_at
    
    @classmethod
    def from_json(cls, data):
        return cls(**data)

    def to_json(self):
        to_serialize = ['id', 'title', 'text', 'created_at', 'created_by']
        data = {}
        for attr_name in to_serialize:
            data[attr_name] = getattr(self, attr_name)
        return data


if __name__ == '__main__':
    Base.metadata.drop_all(db)
    Base.metadata.create_all(db)

    user = User('test@test.ru', bcrypt.hashpw('qwe123'.encode('utf-8'), bcrypt.gensalt()))

    session.add(user)
    session.commit()

    session.add_all([Item(i, i*2, user.id) for i in range(3)])
    session.commit()