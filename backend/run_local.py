import os
import uvicorn
from app.core.database import engine
from app.models import Base

# Initialize the database
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
