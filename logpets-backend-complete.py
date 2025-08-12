# LogPets PRO - Sistema Completo Backend
# FastAPI + PostgreSQL + JWT Auth + GPS Tracking + ReportLab

import os
import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.units import inch
import asyncio
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
import json

# Configurações
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://logpets_user:logpets_password@localhost:5432/logpets_pro")
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== MODELS ====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    vehicles = relationship("Vehicle", back_populates="owner")
    trips = relationship("Trip", back_populates="driver")

class Vehicle(Base):
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer)
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    owner = relationship("User", back_populates="vehicles")
    trips = relationship("Trip", back_populates="vehicle")

class Trip(Base):
    __tablename__ = "trips"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    driver_id = Column(Integer, ForeignKey("users.id"))
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    start_km = Column(Float, nullable=False)
    end_km = Column(Float)
    total_km = Column(Float)
    trip_value = Column(Float)
    fuel_cost = Column(Float)
    toll_cost = Column(Float)
    extra_costs = Column(Float)
    total_cost = Column(Float)
    profit = Column(Float)
    profit_margin = Column(Float)
    status = Column(String, default="em_andamento")  # em_andamento, concluida, cancelada
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    vehicle = relationship("Vehicle", back_populates="trips")
    driver = relationship("User", back_populates="trips")
    gps_locations = relationship("GPSLocation", back_populates="trip")

class GPSLocation(Base):
    __tablename__ = "gps_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamento
    trip = relationship("Trip", back_populates="gps_locations")

class Fine(Base):
    __tablename__ = "fines"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    fine_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False)
    location = Column(String)
    status = Column(String, default="pendente")  # pendente, paga, contestada
    document_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# ==================== SCHEMAS ====================

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime

class VehicleCreate(BaseModel):
    license_plate: str
    model: str
    year: Optional[int] = None

class VehicleResponse(BaseModel):
    id: int
    license_plate: str
    model: str
    year: Optional[int]
    is_active: bool
    created_at: datetime

class TripCreate(BaseModel):
    vehicle_id: int
    origin: str
    destination: str
    start_date: datetime
    start_km: float
    trip_value: Optional[float] = 0

class TripUpdate(BaseModel):
    end_date: Optional[datetime] = None
    end_km: Optional[float] = None
    fuel_cost: Optional[float] = 0
    toll_cost: Optional[float] = 0
    extra_costs: Optional[float] = 0

class TripResponse(BaseModel):
    id: int
    vehicle_id: int
    driver_id: int
    origin: str
    destination: str
    start_date: datetime
    end_date: Optional[datetime]
    start_km: float
    end_km: Optional[float]
    total_km: Optional[float]
    trip_value: Optional[float]
    total_cost: Optional[float]
    profit: Optional[float]
    profit_margin: Optional[float]
    status: str
    created_at: datetime

class GPSLocationCreate(BaseModel):
    trip_id: int
    latitude: float
    longitude: float
    speed: Optional[float] = None

class Token(BaseModel):
    access_token: str
    token_type: str

# ==================== SECURITY ====================

security = HTTPBearer()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ==================== DATABASE ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), username: str = Depends(verify_token)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

# ==================== SERVICES ====================

class PDFGenerator:
    @staticmethod
    def generate_trip_report(trips: List[Trip], user: User) -> str:
        filename = f"relatorio_viagens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = f"static/pdfs/{filename}"
        
        # Criar diretório se não existir
        os.makedirs("static/pdfs", exist_ok=True)
        
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        
        # Cabeçalho
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "LogPets PRO - Relatório de Viagens")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Usuário: {user.full_name}")
        c.drawString(50, height - 100, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        # Dados das viagens
        y_position = height - 150
        
        for trip in trips:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y_position, f"Viagem #{trip.id}")
            y_position -= 20
            
            c.setFont("Helvetica", 10)
            c.drawString(70, y_position, f"Origem: {trip.origin}")
            y_position -= 15
            c.drawString(70, y_position, f"Destino: {trip.destination}")
            y_position -= 15
            c.drawString(70, y_position, f"KM Total: {trip.total_km or 'N/A'}")
            y_position -= 15
            c.drawString(70, y_position, f"Valor: R$ {trip.trip_value or 0:.2f}")
            y_position -= 15
            c.drawString(70, y_position, f"Lucro: R$ {trip.profit or 0:.2f}")
            y_position -= 30
            
            if y_position < 100:
                c.showPage()
                y_position = height - 50
        
        c.save()
        return filepath

class EmailService:
    @staticmethod
    def send_report_email(recipient: str, pdf_path: str, subject: str = "Relatório LogPets PRO"):
        try:
            # Configurar SMTP (substitua pelas suas configurações)
            smtp_server = "smtp.gmail.com"  # Exemplo para Gmail
            smtp_port = 587
            sender_email = "your-email@gmail.com"
            sender_password = "your-app-password"
            
            msg = MimeMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient
            msg['Subject'] = subject
            
            body = "Segue em anexo o relatório solicitado do LogPets PRO."
            msg.attach(MimeText(body, 'plain'))
            
            # Anexar PDF
            with open(pdf_path, "rb") as attachment:
                part = MimeBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(pdf_path)}'
                )
                msg.attach(part)
            
            # Enviar email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, recipient, text)
            server.quit()
            
            return True
        except Exception as e:
            print(f"Erro ao enviar email: {e}")
            return False

# ==================== APP SETUP ====================

app = FastAPI(
    title="LogPets PRO API",
    description="Sistema completo de gestão de transporte de animais",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Criar tabelas
Base.metadata.create_all(bind=engine)

# ==================== ROUTES ====================

@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Verificar se usuário já existe
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username já existe")
    
    # Criar usuário
    hashed_password = hash_password(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@app.post("/auth/login", response_model=Token)
async def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Usuário inativo")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/vehicles/", response_model=VehicleResponse)
async def create_vehicle(vehicle: VehicleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verificar se placa já existe
    if db.query(Vehicle).filter(Vehicle.license_plate == vehicle.license_plate).first():
        raise HTTPException(status_code=400, detail="Placa já cadastrada")
    
    db_vehicle = Vehicle(
        license_plate=vehicle.license_plate,
        model=vehicle.model,
        year=vehicle.year,
        owner_id=current_user.id
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    
    return db_vehicle

@app.get("/vehicles/", response_model=List[VehicleResponse])
async def get_vehicles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Vehicle).filter(Vehicle.owner_id == current_user.id).all()

@app.post("/trips/", response_model=TripResponse)
async def create_trip(trip: TripCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verificar se veículo existe e pertence ao usuário
    vehicle = db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id, Vehicle.owner_id == current_user.id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    
    db_trip = Trip(
        vehicle_id=trip.vehicle_id,
        driver_id=current_user.id,
        origin=trip.origin,
        destination=trip.destination,
        start_date=trip.start_date,
        start_km=trip.start_km,
        trip_value=trip.trip_value
    )
    db.add(db_trip)
    db.commit()
    db.refresh(db_trip)
    
    return db_trip

@app.put("/trips/{trip_id}", response_model=TripResponse)
async def update_trip(trip_id: int, trip_update: TripUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.driver_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    
    # Atualizar campos
    if trip_update.end_date:
        trip.end_date = trip_update.end_date
    if trip_update.end_km:
        trip.end_km = trip_update.end_km
        trip.total_km = trip_update.end_km - trip.start_km
    
    trip.fuel_cost = trip_update.fuel_cost or 0
    trip.toll_cost = trip_update.toll_cost or 0
    trip.extra_costs = trip_update.extra_costs or 0
    
    # Calcular custos totais
    trip.total_cost = trip.fuel_cost + trip.toll_cost + trip.extra_costs
    trip.profit = (trip.trip_value or 0) - trip.total_cost
    
    if trip.trip_value and trip.trip_value > 0:
        trip.profit_margin = (trip.profit / trip.trip_value) * 100
    
    if trip.end_date:
        trip.status = "concluida"
    
    db.commit()
    db.refresh(trip)
    
    return trip

@app.get("/trips/", response_model=List[TripResponse])
async def get_trips(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Trip).filter(Trip.driver_id == current_user.id).all()

@app.post("/gps/location")
async def save_gps_location(location: GPSLocationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verificar se a viagem existe e pertence ao usuário
    trip = db.query(Trip).filter(Trip.id == location.trip_id, Trip.driver_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    
    db_location = GPSLocation(
        trip_id=location.trip_id,
        latitude=location.latitude,
        longitude=location.longitude,
        speed=location.speed
    )
    db.add(db_location)
    db.commit()
    
    return {"message": "Localização GPS salva com sucesso"}

@app.get("/gps/trip/{trip_id}")
async def get_trip_gps_locations(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verificar se a viagem existe e pertence ao usuário
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.driver_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    
    locations = db.query(GPSLocation).filter(GPSLocation.trip_id == trip_id).all()
    return locations

@app.get("/reports/trips/pdf")
async def generate_trips_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trips = db.query(Trip).filter(Trip.driver_id == current_user.id).all()
    
    pdf_path = PDFGenerator.generate_trip_report(trips, current_user)
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"relatorio_viagens_{current_user.username}.pdf"
    )

@app.post("/reports/email")
async def send_report_email(email: EmailStr, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trips = db.query(Trip).filter(Trip.driver_id == current_user.id).all()
    
    pdf_path = PDFGenerator.generate_trip_report(trips, current_user)
    
    success = EmailService.send_report_email(
        recipient=email,
        pdf_path=pdf_path,
        subject=f"Relatório LogPets PRO - {current_user.full_name}"
    )
    
    if success:
        return {"message": "Relatório enviado por email com sucesso"}
    else:
        raise HTTPException(status_code=500, detail="Erro ao enviar email")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # Validar tipo de arquivo
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não permitido")
    
    # Gerar nome único
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"static/uploads/{unique_filename}"
    
    # Criar diretório se não existir
    os.makedirs("static/uploads", exist_ok=True)
    
    # Salvar arquivo
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return {"filename": unique_filename, "file_path": file_path}

@app.get("/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_trips = db.query(Trip).filter(Trip.driver_id == current_user.id).count()
    active_trips = db.query(Trip).filter(Trip.driver_id == current_user.id, Trip.status == "em_andamento").count()
    total_vehicles = db.query(Vehicle).filter(Vehicle.owner_id == current_user.id).count()
    
    # Calcular lucro total
    completed_trips = db.query(Trip).filter(Trip.driver_id == current_user.id, Trip.status == "concluida").all()
    total_profit = sum(trip.profit or 0 for trip in completed_trips)
    
    return {
        "total_trips": total_trips,
        "active_trips": active_trips,
        "total_vehicles": total_vehicles,
        "total_profit": total_profit
    }

@app.get("/")
async def root():
    return {"message": "LogPets PRO API v1.0.0 - Sistema de Gestão de Transporte de Animais"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== ADMIN ROUTES ====================

@app.get("/admin/users", response_model=List[UserResponse])
async def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    return db.query(User).all()

@app.get("/admin/trips", response_model=List[TripResponse])
async def get_all_trips(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    return db.query(Trip).all()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)