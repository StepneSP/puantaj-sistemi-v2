import streamlit as st
from datetime import date, datetime, time, timedelta
import pandas as pd

from db import get_employee_by_id_card
from db import (
    init_db, add_employee, get_employees, get_employee_by_card,
    save_punch, get_punches, get_daily_rows, get_monthly_rows,
    get_employee_month_detail, add_adjustment, get_adjustments,
    add_leave, get_leaves, add_holiday, get_holidays, get_setting,
    set_setting
)

st.set_page_config(page_title="Puantaj Sistemi", page_icon="💳", layout="wide")
init_db()

st.title("💳 Puantaj Sistemi")

def month_bounds(d):
    first = d.replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return first, last

def weekly_seventh_day(dates):
    by_week = {}
    for d in dates:
        monday = d - timedelta(days=d.weekday())
        by_week.setdefault(monday, set()).add(d)
    return sum(1 for days in by_week.values() if len(days) >= 7)

page = st.sidebar.radio(
    "Menü",
    ["📊 Dashboard", "💳 Kart Okutma", "👥 Personeller",
     "📅 Puantaj", "📝 Düzeltmeler / İzin", "📈 Raporlar", "⚙️ Ayarlar"]
)

# ---------------- Dashboard ----------------
if page == "📊 Dashboard":
    st.subheader("Bugünkü Durum")
    selected = st.date_input("Tarih", value=date.today())
    rows = get_daily_rows(selected)
    total = len(get_employees(True))
    present = sum(1 for r in rows if r["Durum"] == "Geldi")
    missing = total - present
    seventh = sum(1 for r in rows if r["7. Gün"] == "Evet")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktif personel", total)
    c2.metric("Gelen", present)
    c3.metric("Gelmedi", missing)
    c4.metric("7. gün çalışan", seventh)

    st.divider()
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------- Card Reader ----------------
elif page == "💳 Kart Okutma":
    st.subheader("Kart Okutma")
    st.caption("Klavye tipi okuyucuda bu alan seçiliyken kartı okutun. Okuyucu Enter gönderiyorsa kayıt otomatik oluşur.")

    if "reader_value" not in st.session_state:
        st.session_state.reader_value = ""

    with st.form("reader_form", clear_on_submit=True):
        card = st.text_input(
            "Kart numarası",
            placeholder="Kartı okutun...",
            label_visibility="collapsed",
            autofocus=True
        )
        submit = st.form_submit_button("Kartı Kaydet", use_container_width=True)

    if submit and card.strip():
        card = card.strip()
        emp = get_employee_by_card(card)
        if emp is None:
            st.error(f"Kayıtlı olmayan kart: {card}")
        else:
            now = datetime.now()
            save_punch(emp["id"], card, now)
            st.success(f"✓ {emp['name']} — {now.strftime('%d.%m.%Y %H:%M:%S')} kaydedildi.")
            st.rerun()

    st.markdown("### Son okutmalar")
    recent = get_punches(date.today(), date.today())
    st.dataframe(recent.head(30), use_container_width=True, hide_index=True)

# ---------------- Employees ----------------
elif page == "👥 Personeller":
    st.subheader("Personel ve Kart Yönetimi")

    with st.expander("➕ Yeni personel / kart tanımla", expanded=True):
        with st.form("new_employee"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Ad Soyad *")
            employee_no = c2.text_input("Personel No")
            c3, c4 = st.columns(2)
            card_no = c3.text_input("Kart No * — kartı okutabilirsiniz")
            department = c4.text_input("Departman")
            c5, c6 = st.columns(2)
            shift_start = c5.time_input("Vardiya başlangıcı", value=time(8, 0))
            shift_end = c6.time_input("Vardiya bitişi", value=time(17, 0))
            submitted = st.form_submit_button("Personeli Kaydet", use_container_width=True)

            if submitted:
                if not name.strip() or not card_no.strip():
                    st.error("Ad Soyad ve Kart No zorunludur.")
                elif get_employee_by_card(card_no.strip()):
                    st.error("Bu kart zaten kayıtlı.")
                else:
                    add_employee(name.strip(), employee_no.strip(), card_no.strip(),
                                 department.strip(), shift_start.strftime("%H:%M"),
                                 shift_end.strftime("%H:%M"))
                    st.success(f"{name} kaydedildi.")
                    st.rerun()

    emps = get_employees(False)
    if emps:
        df = pd.DataFrame(emps)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------- Attendance ----------------
elif page == "📅 Puantaj":
    st.subheader("Aylık Puantaj")
    selected = st.date_input("Ay", value=date.today())
    first, last = month_bounds(selected)
    rows = get_monthly_rows(first, last)
    df = pd.DataFrame(rows)

    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ CSV indir",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"puantaj_{first:%Y_%m}.csv",
            mime="text/csv"
        )
    else:
        st.info("Bu ay kayıt bulunamadı.")

# ---------------- Adjustments / Leave ----------------
elif page == "📝 Düzeltmeler / İzin":
    st.subheader("Manuel Düzeltme ve İzin")

    emps = get_employees(True)
    if not emps:
        st.warning("Önce personel tanımlayın.")
    else:
        emp_map = {f'{e["name"]} ({e["employee_no"]})': e["id"] for e in emps}
        label = st.selectbox("Personel", list(emp_map.keys()))
        emp_id = emp_map[label]

        tab1, tab2 = st.tabs(["Kart hareketi düzeltmesi", "İzin"])

        with tab1:
            with st.form("adjustment"):
                d = st.date_input("Tarih", value=date.today())
                kind = st.selectbox("İşlem", ["Giriş ekle", "Çıkış ekle"])
                t = st.time_input("Saat", value=time(8, 0))
                note = st.text_input("Açıklama")
                ok = st.form_submit_button("Kaydet")
                if ok:
                    save_punch(emp_id, get_employee_by_id_card(emp_id), datetime.combine(d, t), source="MANUEL")
                    add_adjustment(emp_id, d, kind, t.strftime("%H:%M"), note)
                    st.success("Manuel kayıt eklendi.")

        with tab2:
            with st.form("leave"):
                d1 = st.date_input("Başlangıç", value=date.today())
                d2 = st.date_input("Bitiş", value=date.today())
                leave_type = st.selectbox("İzin türü", ["Yıllık izin", "Rapor", "Ücretsiz izin", "Diğer"])
                note = st.text_input("Not", key="leave_note")
                ok = st.form_submit_button("İzni kaydet")
                if ok:
                    if d2 < d1:
                        st.error("Bitiş tarihi başlangıçtan önce olamaz.")
                    else:
                        add_leave(emp_id, d1, d2, leave_type, note)
                        st.success("İzin kaydedildi.")

        st.divider()
        st.write("Son manuel düzeltmeler")
        st.dataframe(pd.DataFrame(get_adjustments()), use_container_width=True, hide_index=True)

# ---------------- Reports ----------------
elif page == "📈 Raporlar":
    st.subheader("Aylık Rapor")
    selected = st.date_input("Ay", value=date.today(), key="report_month")
    first, last = month_bounds(selected)
    rows = get_monthly_rows(first, last)
    df = pd.DataFrame(rows)

    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Excel'de açılabilir CSV indir",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"puantaj_rapor_{first:%Y_%m}.csv",
            mime="text/csv"
        )

# ---------------- Settings ----------------
elif page == "⚙️ Ayarlar":
    st.subheader("Sistem Ayarları")
    st.write("Bu sürümde kurumun puantaj kuralları aşağıdaki şekilde sabitlenmiştir.")

    c1, c2 = st.columns(2)
    c1.metric("Normal haftalık gün", 6)
    c2.metric("7. gün ek mesai", "9 saat")

    st.info("Hafta Pazartesi–Pazar kabul edilir. Aynı haftada 7 farklı çalışma günü varsa +9 saat ek mesai oluşur. Mola ayrı hesaplanmaz.")
    st.caption("Not: Resmî bordro/iş hukuku hesabı için kurumunuzun insan kaynakları ve muhasebe kuralları ayrıca doğrulanmalıdır.")
