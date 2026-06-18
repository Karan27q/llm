from app.database import db_session

class BaseRepository:
    def __init__(self):
        self.session = db_session

    def commit(self):
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

    def add(self, entity):
        self.session.add(entity)
        return entity

    def delete(self, entity):
        self.session.delete(entity)
