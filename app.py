import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, time, timedelta
import pandas as pd

from db import (
    init_db, add_employee, get_employees, get_employee_by_card,
    save_punch, get_punches, get_daily_rows, get_monthly_rows,
    get_employee_month_detail, add_adjustment, get_adjustments,
    add_leave, get_leaves, add_holiday, get_holidays, get_setting,
    set_setting, get_employee_by_id_card,
    register_card_punch, now_tr, today_tr
)

st.set_page_config(page_title="Puantaj Sistemi", page_icon="💳", layout="wide")
init_db()

st.title("💳 Puantaj Sistemi")


def month_bounds(d):
    first = d.replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return first, last


def flash(kind, message):
    """st.rerun() mesajı sildiği için, mesajı bir sonraki çalıştırmada göstermek üzere saklar."""
    st.session_state["_flash"] = (kind, message)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        kind, message = item
        getattr(st, kind)(message)


def focus_card_input(token):
    """Kart alanına imleci geri verir (kiosk kullanımı için, en iyi çaba).

    `token` her okutmada değiştiği için HTML farklılaşır ve script yeniden çalışır.
    Streamlit'in iç yapısına bağlı olduğundan çalışmazsa sessizce atlanır.
    """
    components.html(f"""
    <script>
    // okutma #{token}
    (function () {{
        let tries = 0;
        const timer = setInterval(function () {{
            try {{
                const el = window.parent.document.querySelector('input[aria-label="Kart numarası"]');
                if (el) {{ el.focus(); clearInterval(timer); }}
            }} catch (e) {{ clearInterval(timer); }}
            if (++tries > 20) clearInterval(timer);
        }}, 100);
    }})();
    </script>
    """, height=0)


page = st.sidebar.radio(
    "Menü",
    ["📊 Dashboard", "💳 Kart Okutma", "👥 Personeller",
     "📅 Puantaj", "📝 Düzeltmeler / İzin", "📈 Raporlar", "⚙️ Ayarlar"]
)

# ---------------- Dashboard ----------------
if page == "📊 Dashboard":
    st.subheader("Bugünkü Durum")
    selected = st.date_input("Tarih", value=today_tr())
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

    if "scan_count" not in st.session_state:
        st.session_state.scan_count = 0

    with st.form("reader_form", clear_on_submit=True):
        card = st.text_input(
            "Kart numarası",
            placeholder="Kartı okutun...",
            label_visibility="collapsed"
        )
        submit = st.form_submit_button("Kartı Kaydet", use_container_width=True)

    # Sonuç mesajı kayıttan sonra aynı çalıştırmada çizilir; st.rerun() gerekmez,
    # bu yüzden mesaj ekranda kalır. Aşağıdaki tablo da kayıttan sonra okunur.
    if submit and card.strip():
        st.session_state.scan_count += 1
        result = register_card_punch(card.strip())
        emp = result["employee"]
        stamp = result["timestamp"].strftime("%d.%m.%Y %H:%M:%S")

        if result["status"] == "unknown":
            st.error(f"Kayıtlı olmayan kart: {card.strip()}")
        elif result["status"] == "duplicate":
            st.warning(
                f"{emp['name']} kartı az önce ({result['last_timestamp']:%H:%M:%S}) okutuldu. "
                f"Tekrar okutma yok sayıldı; yeni okutma için ~{result['wait_seconds']} sn bekleyin."
            )
        else:
            label = "Giriş" if result["status"] == "in" else "Çıkış"
            st.success(f"Personel {label}: {emp['name']} — {stamp}")

    st.markdown("### Son okutmalar")
    recent = get_punches(today_tr(), today_tr())
    st.dataframe(recent.head(30), use_container_width=True, hide_index=True)

    focus_card_input(st.session_state.scan_count)

# ---------------- Employees ----------------
elif page == "👥 Personeller":
    st.subheader("Personel ve Kart Yönetimi")
    show_flash()

    with st.expander("➕ Yeni personel / kart tanımla", expanded=True):
        with st.form("new_employee"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Ad Soyad *")
            employee_no = c2.text_input("Personel No")
            c3, c4 = st.columns(2)
            card_no = c3.text_input("Kart No * — kartı okutabilirsiniz")
            department = c4.text_input("Departman")
            submitted = st.form_submit_button("Personeli Kaydet", use_container_width=True)

        if submitted:
            if not name.strip() or not card_no.strip():
                st.error("Ad Soyad ve Kart No zorunludur.")
            elif get_employee_by_card(card_no.strip()):
                st.error("Bu kart zaten kayıtlı.")
            else:
                add_employee(name.strip(), employee_no.strip(), card_no.strip(),
                             department.strip())
                flash("success", f"{name.strip()} kaydedildi.")
                st.rerun()

    emps = get_employees(False)
    if emps:
        df = pd.DataFrame(emps)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------- Attendance ----------------
elif page == "📅 Puantaj":
    st.subheader("Aylık Puantaj")
    selected = st.date_input("Ay", value=today_tr())
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
                d = st.date_input("Tarih", value=today_tr())
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
                d1 = st.date_input("Başlangıç", value=today_tr())
                d2 = st.date_input("Bitiş", value=today_tr())
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
    selected = st.date_input("Ay", value=today_tr(), key="report_month")
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
