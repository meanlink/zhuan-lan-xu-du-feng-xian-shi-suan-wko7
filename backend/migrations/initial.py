from src.config.database import Base, engine
from src import models
def migrate():
    Base.metadata.create_all(engine)
if __name__=='__main__':migrate()
