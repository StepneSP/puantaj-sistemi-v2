import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

DB_PATH = Path("data/puantaj.db")

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_no TEXT,
            card_no TEXT NOT NULL UNIQUE,
            department TEXT,
            shift_start TEXT DEFAULT '08:00',
            shift_end TEXT DEFAULT '17:00',
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS punches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            card_no TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source TEXT DEFAULT 'CARD'
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            kind TEXT NOT NULL,
            time TEXT NOT NULL,
            note TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            note TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS holidays (
            date TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('weekly_normal_days','6')")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('seventh_day_overtime_hours','9')")
        c.commit()

def add_employee(name, employee_no, card_no, department, shift_start, shift_end):
    with conn() as c:
        c.execute("""INSERT INTO employees
        (name,employee_no,card_no,department,shift_start,shift_end,created_at)
        VALUES(?,?,?,?,?,?,?)""",
        (name, employee_no, card_no, department, shift_start, shift_end,
         datetime.now().isoformat(timespec="seconds")))
        c.commit()

def get_employees(active_only=True):
    with conn() as c:
        q = "SELECT * FROM employees"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY name"
        return [dict(r) for r in c.execute(q).fetchall()]

def get_employee_by_card(card_no):
    with conn() as c:
        r = c.execute("SELECT * FROM employees WHERE card_no=? AND active=1", (card_no,)).fetchone()
        return dict(r) if r else None

def get_employee_by_id(employee_id):
    with conn() as c:
        r = c.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
        return dict(r) if r else None

def get_employee_by_id_card(employee_id):
    e = get_employee_by_id(employee_id)
    return e["card_no"]

def save_punch(employee_id, card_no, timestamp, source="CARD"):
    with conn() as c:
        c.execute("INSERT INTO punches(employee_id,card_no,timestamp,source) VALUES(?,?,?,?)",
                  (employee_id, card_no, timestamp.isoformat(timespec="seconds"), source))
        c.commit()

def get_punches(start_date, end_date):
    with conn() as c:
        rows = c.execute("""
        SELECT p.id, e.name AS Personel, e.employee_no AS [Personel No],
               p.card_no AS [Kart No], p.timestamp AS [Tarih-Saat], p.source AS Kaynak
        FROM punches p JOIN employees e ON e.id=p.employee_id
        WHERE date(p.timestamp) BETWEEN ? AND ?
        ORDER BY p.timestamp DESC
        """, (start_date.isoformat(), end_date.isoformat())).fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def _punch_df(start_date, end_date):
    with conn() as c:
        rows = c.execute("""
        SELECT p.employee_id,e.name,e.employee_no,e.card_no,e.department,p.timestamp
        FROM punches p JOIN employees e ON e.id=p.employee_id
        WHERE date(p.timestamp) BETWEEN ? AND ?
        ORDER BY p.timestamp
        """, (start_date.isoformat(), end_date.isoformat())).fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def _leave_dates(employee_id, start_date, end_date):
    dates=set()
    with conn() as c:
        rows=c.execute("""SELECT start_date,end_date FROM leaves
                          WHERE employee_id=? AND end_date>=? AND start_date<=?""",
                       (employee_id,start_date.isoformat(),end_date.isoformat())).fetchall()
    for r in rows:
        a=datetime.fromisoformat(r["start_date"]).date()
        b=datetime.fromisoformat(r["end_date"]).date()
        cur=max(a,start_date)
        end=min(b,end_date)
        while cur<=end:
            dates.add(cur)
            cur += timedelta(days=1)
    return dates

def _holiday_dates(start_date,end_date):
    with conn() as c:
        rows=c.execute("SELECT date FROM holidays WHERE date BETWEEN ? AND ?",
                       (start_date.isoformat(),end_date.isoformat())).fetchall()
    return {datetime.fromisoformat(r["date"]).date() for r in rows}

def _work_dates(df):
    result={}
    if df.empty: return result
    df=df.copy()
    df["dt"]=pd.to_datetime(df["timestamp"])
    df["date"]=df["dt"].dt.date
    for emp_id,g in df.groupby("employee_id"):
        result[emp_id]=set(g["date"].tolist())
    return result

def _seventh_day_dates(dates):
    by_week={}
    for d in dates:
        monday=d-timedelta(days=d.weekday())
        by_week.setdefault(monday,set()).add(d)
    seventh=set()
    for days in by_week.values():
        if len(days)>=7:
            # The 7th working date in Mon-Sun. With seven dates, this is Sunday.
            seventh.add(sorted(days)[6])
    return seventh

def get_daily_rows(selected_date):
    emps=get_employees(True)
    df=_punch_df(selected_date,selected_date)
    holiday_dates=_holiday_dates(selected_date,selected_date)
    rows=[]
    for e in emps:
        g=df[df.employee_id==e["id"]] if not df.empty else pd.DataFrame()
        times=sorted(pd.to_datetime(g["timestamp"]).tolist()) if not g.empty else []
        first=times[0].strftime("%H:%M") if times else "-"
        last=times[-1].strftime("%H:%M") if len(times)>1 else "-"
        # Determine 7th day using a small surrounding week.
        monday=selected_date-timedelta(days=selected_date.weekday())
        sunday=monday+timedelta(days=6)
        wg=_punch_df(monday,sunday)
        dates=set(pd.to_datetime(wg[wg.employee_id==e["id"]]["timestamp"]).dt.date.tolist()) if not wg.empty else set()
        is7=selected_date in _seventh_day_dates(dates)
        status="Geldi" if times else ("Resmî Tatil" if selected_date in holiday_dates else "Gelmedi")
        rows.append({"Personel":e["name"],"Departman":e["department"],"Giriş":first,
                     "Çıkış":last,"7. Gün":"Evet" if is7 else "Hayır","Durum":status})
    return rows

def get_monthly_rows(start_date,end_date):
    emps=get_employees(False)
    df=_punch_df(start_date,end_date)
    work_dates=_work_dates(df)
    holidays=_holiday_dates(start_date,end_date)
    rows=[]
    for e in emps:
        dates=set(work_dates.get(e["id"],set()))
        leave_dates=_leave_dates(e["id"],start_date,end_date)
        seventh=_seventh_day_dates(dates)
        rows.append({
            "Personel":e["name"],"Personel No":e["employee_no"],"Departman":e["department"],
            "Puantaj (gün)":len(dates),
            "7. Gün Çalışma":len(seventh),
            "Ek Mesai (saat)":len(seventh)*int(get_setting("seventh_day_overtime_hours","9")),
            "İzin (gün)":len(leave_dates),
            "Resmî Tatil (ay)":len(holidays)
        })
    return rows

def get_employee_month_detail(employee_id,start_date,end_date):
    df=_punch_df(start_date,end_date)
    g=df[df.employee_id==employee_id] if not df.empty else pd.DataFrame()
    dates=sorted(set(pd.to_datetime(g.timestamp).dt.date.tolist())) if not g.empty else []
    seventh=_seventh_day_dates(set(dates))
    rows=[]
    for d in dates:
        gg=g[pd.to_datetime(g.timestamp).dt.date==d]
        ts=sorted(pd.to_datetime(gg.timestamp).tolist())
        rows.append({"Tarih":d,"Giriş":ts[0].strftime("%H:%M"),"Çıkış":ts[-1].strftime("%H:%M") if len(ts)>1 else "-",
                     "7. Gün":"Evet" if d in seventh else "Hayır"})
    return rows

def add_adjustment(employee_id,d,kind,t,note):
    with conn() as c:
        c.execute("INSERT INTO adjustments(employee_id,date,kind,time,note) VALUES(?,?,?,?,?)",
                  (employee_id,d.isoformat(),kind,t,note))
        c.commit()

def get_adjustments():
    with conn() as c:
        rows=c.execute("""SELECT a.date AS Tarih,e.name AS Personel,a.kind AS İşlem,
                          a.time AS Saat,a.note AS Açıklama
                          FROM adjustments a JOIN employees e ON e.id=a.employee_id
                          ORDER BY a.id DESC""").fetchall()
    return [dict(r) for r in rows]

def add_leave(employee_id,start_date,end_date,leave_type,note):
    with conn() as c:
        c.execute("""INSERT INTO leaves(employee_id,start_date,end_date,leave_type,note)
                     VALUES(?,?,?,?,?)""",
                  (employee_id,start_date.isoformat(),end_date.isoformat(),leave_type,note))
        c.commit()

def get_leaves():
    with conn() as c:
        rows=c.execute("""SELECT l.start_date AS Başlangıç,l.end_date AS Bitiş,
                          e.name AS Personel,l.leave_type AS [İzin Türü],l.note AS Not
                          FROM leaves l JOIN employees e ON e.id=l.employee_id
                          ORDER BY l.start_date DESC""").fetchall()
    return [dict(r) for r in rows]

def add_holiday(d,name):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO holidays(date,name) VALUES(?,?)",(d.isoformat(),name))
        c.commit()

def get_holidays():
    with conn() as c:
        rows=c.execute("SELECT date AS Tarih,name AS [Tatil Adı] FROM holidays ORDER BY date").fetchall()
    return [dict(r) for r in rows]

def get_setting(key,default=None):
    with conn() as c:
        r=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
    return r["value"] if r else default

def set_setting(key,value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,str(value)))
        c.commit()
