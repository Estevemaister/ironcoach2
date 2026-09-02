from datetime import date, datetime, timedelta, timezone
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from .config import settings

Base=declarative_base()
engine=create_engine(settings.database_url,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')

class User(Base):
    __tablename__='users'; id=Column(Integer,primary_key=True); email=Column(String(255),unique=True,index=True,nullable=False); password_hash=Column(String(255),nullable=False); athlete=relationship('Athlete',back_populates='user',uselist=False,cascade='all, delete-orphan')
class Athlete(Base):
    __tablename__='athletes'; id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey('users.id'),unique=True,nullable=False); name=Column(String(120),nullable=False); race_name=Column(String(200),default='IRONMAN 70.3 Valencia 2027'); race_date=Column(Date); weight_kg=Column(Float); swim_level=Column(String(30),default='beginner'); bike_level=Column(String(30),default='beginner'); run_level=Column(String(30),default='beginner'); weekly_hours_target=Column(Float,default=8); user=relationship('User',back_populates='athlete')
class DailyState(Base):
    __tablename__='daily_states'; id=Column(Integer,primary_key=True); athlete_id=Column(Integer,ForeignKey('athletes.id'),index=True); date=Column(Date,index=True); fitness=Column(Float,default=50); fatigue=Column(Float,default=20); recovery=Column(Float,default=75); readiness=Column(Float,default=70); consistency=Column(Float,default=70); injury_risk=Column(Float,default=20); finish_confidence=Column(Float,default=30); last_load=Column(Float,default=0); reason=Column(Text,default='')
class TrainingPlan(Base):
    __tablename__='training_plans'; id=Column(Integer,primary_key=True); athlete_id=Column(Integer,ForeignKey('athletes.id'),index=True); version=Column(Integer,default=1); status=Column(String(20),default='active'); created_at=Column(DateTime,default=datetime.utcnow)
class TrainingWeek(Base):
    __tablename__='training_weeks'; id=Column(Integer,primary_key=True); plan_id=Column(Integer,ForeignKey('training_plans.id'),index=True); week_start=Column(Date); phase=Column(String(30)); objective_primary=Column(String(150)); load_budget=Column(Float,default=0)
class Workout(Base):
    __tablename__='workouts'; id=Column(Integer,primary_key=True); week_id=Column(Integer,ForeignKey('training_weeks.id'),index=True); scheduled_date=Column(Date,index=True); sport=Column(String(20)); title=Column(String(150)); objective=Column(String(200)); duration_min=Column(Integer); intensity=Column(String(30)); planned_load=Column(Float,default=0); status=Column(String(20),default='planned'); adaptation_reason=Column(Text)
class WorkoutExecution(Base):
    __tablename__='workout_executions'; id=Column(Integer,primary_key=True); workout_id=Column(Integer,ForeignKey('workouts.id')); actual_duration_min=Column(Float); actual_rpe=Column(Float); notes=Column(Text); executed_at=Column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
app=FastAPI(title='IronCoach API',version='0.4.0')
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',') if x.strip()],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

def token(uid): return jwt.encode({'sub':str(uid),'exp':datetime.now(timezone.utc)+timedelta(hours=8)},settings.jwt_secret,algorithm='HS256')
def user_from_request(request,db):
    t=request.cookies.get(settings.auth_cookie_name); h=request.headers.get('Authorization','')
    if not t and h.startswith('Bearer '): t=h[7:]
    if not t: raise HTTPException(401,'Not authenticated')
    try: uid=int(jwt.decode(t,settings.jwt_secret,algorithms=['HS256'])['sub'])
    except Exception: raise HTTPException(401,'Invalid session')
    u=db.query(User).filter_by(id=uid).first()
    if not u or not u.athlete: raise HTTPException(401,'Invalid session')
    return u

def set_session(resp,uid): resp.set_cookie(settings.auth_cookie_name,token(uid),httponly=True,secure=settings.cookie_secure,samesite=settings.cookie_samesite,max_age=8*3600,path='/')
class RegisterIn(BaseModel): email:EmailStr; password:str=Field(min_length=8); name:str
class OnboardingIn(BaseModel): weight_kg:float|None=None; weekly_hours_target:float=8; swim_level:str='beginner'; bike_level:str='beginner'; run_level:str='beginner'; race_name:str='IRONMAN 70.3 Valencia 2027'; race_date:date=date(2027,4,18)
class FeedbackIn(BaseModel): actual_duration_min:float; actual_rpe:float=Field(ge=1,le=10); notes:str=''
class ChatIn(BaseModel): message:str; mode:str='coach'
@app.get('/health')
def health(): return {'status':'ok','service':'ironcoach-api','version':'0.4.0'}
@app.post('/auth/register')
def register(p:RegisterIn):
    db=SessionLocal()
    try:
        if db.query(User).filter_by(email=p.email).first(): raise HTTPException(409,'Email already registered')
        u=User(email=p.email,password_hash=pwd.hash(p.password)); u.athlete=Athlete(name=p.name); db.add(u); db.commit(); db.refresh(u); r=JSONResponse({'ok':True,'user_id':u.id}); set_session(r,u.id); return r
    finally: db.close()
@app.post('/auth/login')
def login(request:Request):
    db=SessionLocal()
    try:
        form=None
        # OAuth2 form is parsed manually to keep the endpoint compatible with the PWA.
        import asyncio
        async def read(): return await request.body()
        raw=asyncio.run(read()).decode()
        from urllib.parse import parse_qs
        q=parse_qs(raw); email=(q.get('username') or [''])[0]; password=(q.get('password') or [''])[0]
        u=db.query(User).filter_by(email=email).first()
        if not u or not pwd.verify(password,u.password_hash): raise HTTPException(401,'Incorrect email or password')
        r=JSONResponse({'access_token':token(u.id),'token_type':'bearer'}); set_session(r,u.id); return r
    finally: db.close()
@app.post('/auth/logout')
def logout():
    r=JSONResponse({'ok':True}); r.delete_cookie(settings.auth_cookie_name,path='/'); return r
@app.post('/auth/onboarding')
def onboarding(p:OnboardingIn,request:Request):
    db=SessionLocal()
    try:
        u=user_from_request(request,db); a=u.athlete; a.weight_kg=p.weight_kg; a.weekly_hours_target=p.weekly_hours_target; a.swim_level=p.swim_level; a.bike_level=p.bike_level; a.run_level=p.run_level; a.race_name=p.race_name; a.race_date=p.race_date; db.commit(); return {'ok':True}
    finally: db.close()
@app.get('/profile')
def profile(request:Request):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete; return {'athlete':{'id':a.id,'name':a.name,'race_name':a.race_name,'race_date':str(a.race_date) if a.race_date else None,'weight_kg':a.weight_kg,'weekly_hours_target':a.weekly_hours_target}}
    finally: db.close()
@app.post('/plan/generate')
def generate(request:Request, race_date:date=date(2027,4,18), limiter:str='bike'):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete
        old=db.query(TrainingPlan).filter_by(athlete_id=a.id,status='active').all()
        for p in old: p.status='archived'
        plan=TrainingPlan(athlete_id=a.id,version=len(old)+1); db.add(plan); db.flush()
        monday=date.today()-timedelta(days=date.today().weekday()); days=[('Swim','Técnica + aeróbico',45,'easy'),('Bike','Sweet Spot',60,'tempo'),('Run','Rodaje fácil',45,'easy'),('Strength','Fuerza + core',40,'easy'),('Swim','Umbral técnico',50,'threshold'),('Bike','Salida larga + brick',135,'z2'),('Run','Tirada larga',70,'z2')]
        for wi in range(6):
            ws=monday+timedelta(days=wi*7); wk=TrainingWeek(plan_id=plan.id,week_start=ws,phase='Base 1',objective_primary='Construir resistencia y consistencia',load_budget=450); db.add(wk); db.flush()
            for di,(sport,title,dur,intensity) in enumerate(days):
                d=ws+timedelta(days=di); db.add(Workout(week_id=wk.id,scheduled_date=d,sport=sport.lower(),title=title,objective='Progresar sin perseguir fatiga',duration_min=dur,intensity=intensity,planned_load=dur*(3 if intensity=='easy' else 5)))
        db.commit(); return {'ok':True,'plan_id':plan.id,'version':plan.version}
    finally: db.close()
@app.get('/plan/current')
def current_plan(request:Request):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete; p=db.query(TrainingPlan).filter_by(athlete_id=a.id,status='active').order_by(TrainingPlan.created_at.desc()).first()
        if not p: return {'plan':None}
        weeks=db.query(TrainingWeek).filter_by(plan_id=p.id).order_by(TrainingWeek.week_start).all(); out=[]
        for w in weeks:
            out.append({'week_start':str(w.week_start),'phase':w.phase,'objective_primary':w.objective_primary,'load_budget':w.load_budget,'workouts':[{'id':x.id,'date':str(x.scheduled_date),'sport':x.sport,'title':x.title,'duration_min':x.duration_min,'intensity':x.intensity,'objective':x.objective,'planned_load':x.planned_load,'status':x.status} for x in db.query(Workout).filter_by(week_id=w.id).order_by(Workout.scheduled_date).all()]})
        return {'plan':{'id':p.id,'version':p.version,'weeks':out}}
    finally: db.close()
@app.get('/today/state')
def today_state(request:Request):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete; s=db.query(DailyState).filter_by(athlete_id=a.id).order_by(DailyState.date.desc()).first()
        if not s:
            s=DailyState(athlete_id=a.id,date=date.today(),fitness=50,fatigue=20,recovery=75,readiness=70,consistency=50,injury_risk=15,finish_confidence=20,reason='Sin suficiente histórico todavía'); db.add(s); db.commit()
        return {'date':str(s.date),'readiness':s.readiness,'recovery':s.recovery,'fatigue':s.fatigue,'fitness':s.fitness,'consistency':s.consistency,'injury_risk':s.injury_risk,'finish_confidence':s.finish_confidence,'last_load':s.last_load,'reason':s.reason}
    finally: db.close()
@app.get('/today/workout')
def today_workout(request:Request):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete; p=db.query(TrainingPlan).filter_by(athlete_id=a.id,status='active').first()
        if not p: return {'workout':None}
        w=db.query(Workout).join(TrainingWeek,Workout.week_id==TrainingWeek.id).filter(TrainingWeek.plan_id==p.id,Workout.scheduled_date>=date.today()).order_by(Workout.scheduled_date).first()
        return {'workout':None if not w else {'id':w.id,'date':str(w.scheduled_date),'sport':w.sport,'title':w.title,'duration_min':w.duration_min,'status':w.status,'objective':w.objective,'intensity':w.intensity,'planned_load':w.planned_load}}
    finally: db.close()
@app.get('/progress')
def progress(request:Request):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete; rows=db.query(DailyState).filter_by(athlete_id=a.id).order_by(DailyState.date).all(); return {'series':[{'date':str(s.date),'fitness':s.fitness,'recovery':s.recovery,'readiness':s.readiness,'consistency':s.consistency,'risk':s.injury_risk,'finish_confidence':s.finish_confidence} for s in rows]}
    finally: db.close()
@app.post('/plan/workouts/{wid}/feedback')
def feedback(wid:int,p:FeedbackIn,request:Request):
    db=SessionLocal()
    try:
        user_from_request(request,db); w=db.query(Workout).filter_by(id=wid).first()
        if not w: raise HTTPException(404,'Workout not found')
        db.add(WorkoutExecution(workout_id=wid,actual_duration_min=p.actual_duration_min,actual_rpe=p.actual_rpe,notes=p.notes)); w.status='completed'; db.commit(); return {'ok':True}
    finally: db.close()
@app.post('/coach/chat')
def coach(p:ChatIn,request:Request):
    db=SessionLocal()
    try:
        a=user_from_request(request,db).athlete; s=db.query(DailyState).filter_by(athlete_id=a.id).order_by(DailyState.date.desc()).first(); r=s.readiness if s else None
        text=p.message.lower(); answer='La decisión de hoy prioriza seguridad, recuperación, objetivo de carrera y tu limiter.'
        if 'readiness' in text or 'recuper' in text: answer=f'Tu readiness actual es {round(r) if r is not None else "aún no disponible"}. No buscamos entrenar duro por entrenar: ajustamos según recuperación y carga.'
        elif 'sesión' in text or 'entreno' in text: answer='La sesión está diseñada para construir adaptación específica sin añadir fatiga innecesaria. Si tu recuperación cae, IronCoach reduce la carga antes de intentar compensarla.'
        return {'text':answer,'mode':p.mode}
    finally: db.close()
