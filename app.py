"""
app.py - Ontology Playground
============================
Jalankan dengan:   streamlit run app.py

Alur besar file ini (baca dari atas ke bawah):
  1. Import + konfigurasi halaman
  2. Muat basis data SQLite dari data/*.csv (src/basis_data.py), sekali per proses
  3. State sesi: objek yang sedang dibuka, riwayat navigasi, percakapan, jejak audit aksi
  4. Sidebar: learning mode, daftar pantau, jejak audit
  5. Tab: Ontology -> Objects -> Graph -> Ask -> SQL -> Data & Sources -> How it works

Semua logika yang bisa diuji ada di src/ (ontologi, basis_data, kueri, graf, aksi); file ini hanya menyusun UI.
Istilah: "tipe objek" = object type, "tautan" = link type, "himpunan objek" = object set, "aksi" = action.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import aksi, basis_data, graf, kueri, ontologi
from src.ontologi import TIPE_OBJEK, TIPE_TAUTAN

# ----------------------------------------------------------------------------
# 0. KONFIGURASI HALAMAN
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Ontology Playground", page_icon="🧩", layout="wide")

TEMPLATE = "plotly_dark"
WARNA_UTAMA = "#fbbf24"
DISCLAIMER = (
    "ℹ️ Provinsi, pelabuhan, komoditas, provinsi penghasil, dan operator pelabuhan adalah data publik yang nyata. "
    "Perusahaan swasta, kapal, pelayaran, dan insiden **disintesis** dengan pola yang realistis (lihat `scripts/bangun_data.py`) "
    "dan tidak menggambarkan entitas yang sungguh ada. Proyek ini demo konsep ontologi untuk belajar dan portofolio pribadi, "
    "bukan sistem operasional dan tidak berafiliasi dengan Palantir atau instansi mana pun."
)


def rapikan(fig: go.Figure, tinggi: int = 380) -> go.Figure:
    """Gaya seragam untuk grafik Plotly: latar transparan, grid tipis."""
    fig.update_layout(template=TEMPLATE, height=tinggi, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=20, t=50, b=10), title=dict(y=0.98, yanchor="top", x=0, xanchor="left", font=dict(size=15)),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#243044", zeroline=False)
    return fig


def angka(n) -> str:
    """1234 -> '1.234' (format Indonesia)."""
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(n):,}".replace(",", ".")


# ----------------------------------------------------------------------------
# 1. MUAT DATA (CSV -> SQLite in-memory, sekali per proses)
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Membangun basis data ontologi...")
def muat():
    kon = basis_data.buat_koneksi()
    return kon, basis_data.hitung_objek(kon), basis_data.hitung_tautan(kon)


kon, JUMLAH_OBJEK, JUMLAH_TAUTAN = muat()
TOTAL_OBJEK, TOTAL_TAUTAN = sum(JUMLAH_OBJEK.values()), sum(JUMLAH_TAUTAN.values())

# ----------------------------------------------------------------------------
# 2. STATE SESI
# ----------------------------------------------------------------------------
st.session_state.setdefault("objek", ("pelabuhan", "IDBPN"))   # (tipe, id) yang sedang dibuka
st.session_state.setdefault("riwayat", [])                      # breadcrumb navigasi
st.session_state.setdefault("audit", [])                        # jejak aksi (src/aksi.py)
st.session_state.setdefault("chat", [])                         # [(peran, isi)]
st.session_state.setdefault("konteks_chat", [])                 # entitas pertanyaan terakhir, untuk "kapal itu"
st.session_state.setdefault("graf_akar", None)                  # (tipe, id) akar graf
st.session_state.setdefault("tipe_jelajah", "pelabuhan")
st.session_state.setdefault("pertanyaan_tertunda", None)


def buka_objek(tipe: str, id_objek: str) -> None:
    """Pindah ke objek lain (pivot). Riwayat disimpan untuk breadcrumb."""
    if st.session_state["objek"] != (tipe, id_objek):
        st.session_state["riwayat"] = (st.session_state["riwayat"] + [st.session_state["objek"]])[-8:]
    st.session_state["objek"] = (tipe, id_objek)
    st.session_state["tipe_jelajah"] = tipe


def judul(tipe: str, id_objek: str) -> str:
    return basis_data.judul_objek(kon, tipe, id_objek)


# ----------------------------------------------------------------------------
# 3. SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("🧩 Ontology Playground")
    st.caption("Objek, tautan, dan pertanyaan: cara kerja ontologi ala Palantir Foundry, dicoba pada data perdagangan laut Indonesia.")
    mode_belajar = st.toggle("🎓 Learning mode", value=False,
                             help="Tampilkan penjelasan konsep, istilah Foundry, dan potongan kode di setiap tab.")
    st.subheader("Ontologi ini")
    for t in TIPE_OBJEK.values():
        st.caption(f"{t.ikon} **{t.label}** · {angka(JUMLAH_OBJEK[t.id])} objek")
    st.caption(f"🔗 **{len(TIPE_TAUTAN)} tipe tautan** · {angka(TOTAL_TAUTAN)} tautan")

    pantau = aksi.daftar_pantau(st.session_state["audit"])
    with st.expander(f"👁️ Daftar pantau ({len(pantau)})", expanded=bool(pantau)):
        if not pantau:
            st.caption("Belum ada kapal yang ditandai. Buka sebuah kapal di tab *Objects* lalu jalankan aksi *Tandai untuk pemeriksaan*.")
        for c in pantau:
            kol1, kol2 = st.columns([4, 1])
            kol1.markdown(f"🚢 **{c.judul}** · prioritas {c.parameter.get('prioritas')}  \n_{c.parameter.get('alasan')}_")
            if kol2.button("Buka", key=f"pantau_{c.id_objek}"):
                buka_objek("kapal", c.id_objek)
                st.rerun()
    with st.expander(f"🧾 Jejak audit ({len(st.session_state['audit'])})"):
        if not st.session_state["audit"]:
            st.caption("Setiap aksi yang dijalankan tercatat di sini: waktu, aksi, objek, parameter.")
        for c in reversed(st.session_state["audit"][-20:]):
            st.caption(f"{c.waktu:%H:%M:%S} · **{aksi.DEFINISI_AKSI[c.aksi].label}** → {TIPE_OBJEK[c.tipe].ikon} {c.judul} · "
                       + ", ".join(f"{k}={v}" for k, v in c.parameter.items()))
    st.caption("Data: `data/*.csv` dibangun oleh `scripts/bangun_data.py` (seed tetap). Lihat tab *Data & Sources*.")

# ----------------------------------------------------------------------------
# 4. JUDUL + ANGKA RINGKASAN
# ----------------------------------------------------------------------------
st.title("🧩 Ontology Playground")
st.markdown(
    "**Connect everything. Then ask it anything.** Demo konsep *ontology* ala Palantir Foundry pada data perdagangan laut Indonesia: "
    "pelabuhan, kapal, komoditas, perusahaan, provinsi, pelayaran, dan insiden saling terhubung lewat tautan bernama, bisa dijelajahi "
    "sebagai objek, digambar sebagai graf, dan ditanyai dengan bahasa sehari-hari."
)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Tipe objek", len(TIPE_OBJEK), help="Object type: Provinsi, Perusahaan, Komoditas, Pelabuhan, Kapal, Pelayaran, Insiden")
k2.metric("Tipe tautan", len(TIPE_TAUTAN), help="Link type: relasi bernama antar dua tipe objek, misalnya Kapal —dimiliki oleh→ Perusahaan")
k3.metric("Objek", angka(TOTAL_OBJEK), help="Jumlah baris di semua tabel objek")
k4.metric("Tautan", angka(TOTAL_TAUTAN), help="Jumlah pasangan objek yang terhubung")
k5.metric("Aksi tersedia", len(aksi.DEFINISI_AKSI), help="Action: perubahan terkendali pada objek yang tercatat di jejak audit")
st.caption(DISCLAIMER)

# ----------------------------------------------------------------------------
# 5. KOMPONEN BERSAMA: tabel objek dan kartu objek
# ----------------------------------------------------------------------------
KOLOM_SEMBUNYI = {"alias", "lat", "lon", "deskripsi"}


def kolom_tampil(tipe: str, df: pd.DataFrame) -> pd.DataFrame:
    """Pilih kolom yang enak dibaca: judul dahulu, lalu properti; kolom penunjuk (…_id) diganti nama objeknya."""
    t = TIPE_OBJEK[tipe]
    hasil = pd.DataFrame(index=df.index)
    urutan = [t.kolom_judul] + [p.nama for p in t.properti if p.nama not in (t.kolom_judul, "id") and p.nama not in KOLOM_SEMBUNYI]
    if t.kolom_judul != "id":
        urutan.append("id")
    for k in urutan:
        if k in df.columns:
            hasil[t.properti_dict()[k].label if k in t.properti_dict() else k] = df[k]
    for l in TIPE_TAUTAN.values():
        if l.tabel == tipe and l.kolom_tujuan in df.columns and l.kolom_tujuan != "id":
            peta = basis_data.semua_objek(kon, l.tujuan).set_index("id")[TIPE_OBJEK[l.tujuan].kolom_judul].to_dict()
            hasil[l.label.capitalize()] = df[l.kolom_tujuan].map(lambda x: peta.get(x, x) if x else "")
    for k in df.columns:
        if k not in hasil.columns and k not in t.properti_dict() and not k.endswith("_id") and k not in KOLOM_SEMBUNYI:
            hasil[k] = df[k]
    return hasil


def tabel_objek(tipe: str, df: pd.DataFrame, key: str, tinggi: int = 360) -> str | None:
    """Tabel objek yang bisa diklik; mengembalikan id baris yang dipilih."""
    if df.empty:
        st.info("Tidak ada objek yang cocok.")
        return None
    tampil = kolom_tampil(tipe, df).reset_index(drop=True)
    ev = st.dataframe(tampil, hide_index=True, width="stretch", height=tinggi, on_select="rerun",
                      selection_mode="single-row", key=key)
    baris = ev.selection.rows if ev and ev.selection else []
    return str(df.iloc[baris[0]]["id"]) if baris else None


def kartu_objek(tipe: str, id_objek: str, key: str, dengan_aksi: bool = True, ringkas: bool = False) -> None:
    """Halaman objek ala Foundry Object View: properti, tautan per tipe, aksi, catatan."""
    t = TIPE_OBJEK[tipe]
    o = basis_data.ambil_objek(kon, tipe, id_objek)
    if o is None:
        st.warning("Objek tidak ditemukan.")
        return
    st.markdown(f"### {t.ikon} {judul(tipe, id_objek)}")
    st.caption(f"{t.label} · `{id_objek}`" + (" · data sintetis" if t.asal == "sintetis" else ""))
    kol_prop, kol_tautan = st.columns([1, 1.3]) if not ringkas else (st.container(), st.container())
    with kol_prop:
        st.markdown("**Properti**")
        baris = []
        for p in t.properti:
            if p.nama == "id" or p.nama not in o or str(o[p.nama]) in ("", "nan", "None"):
                continue
            nilai = o[p.nama]
            if isinstance(nilai, float) and nilai.is_integer():
                nilai = int(nilai)
            if p.tipe == "angka" and isinstance(nilai, (int, float)):
                nilai = f"{angka(nilai)} {p.satuan}".strip()
            baris.append({"Properti": p.label, "Nilai": str(nilai)})
        st.dataframe(pd.DataFrame(baris), hide_index=True, width="stretch", height=min(420, 38 + 35 * len(baris)))
        if "lat" in o and "lon" in o and str(o["lat"]) not in ("", "nan"):
            peta = pd.DataFrame({"lat": [float(o["lat"])], "lon": [float(o["lon"])]})
            st.map(peta, zoom=4, height=180, size=60000, color="#fbbf24")
        catatan = [c for c in aksi.riwayat_objek(st.session_state["audit"], tipe, id_objek)]
        if catatan:
            st.markdown("**Riwayat aksi pada objek ini**")
            for c in catatan:
                st.caption(f"{c.waktu:%H:%M} · {aksi.DEFINISI_AKSI[c.aksi].label} · " + "; ".join(f"{k}: {v}" for k, v in c.parameter.items()))
    with kol_tautan:
        st.markdown("**Tautan**")
        semua = basis_data.tetangga(kon, tipe, id_objek)
        if not any(len(df) for _, _, df in semua):
            st.caption("Objek ini belum punya tautan.")
        for l, tujuan, df in semua:
            if df.empty:
                continue
            tt = TIPE_OBJEK[tujuan]
            with st.expander(f"{l.label} → {tt.ikon} {tt.label} ({len(df)})", expanded=len(df) <= 6 and not ringkas):
                for _, r in df.head(12).iterrows():
                    c1, c2 = st.columns([5, 1])
                    teks = str(r[tt.kolom_judul])
                    if tujuan == "pelayaran":
                        teks = f"{r['id']} · {r['berangkat']} · {r['status']} · {angka(r['muatan'])} ton"
                    elif tujuan == "insiden":
                        teks = f"{r['id']} · {r['tanggal']} · {r['jenis']} ({r['tingkat']})"
                    elif tujuan == "kapal":
                        teks = f"{r['nama']} · {r['jenis']} · {r['bendera']}"
                    elif tujuan == "pelabuhan":
                        teks = f"{r['nama']} · {r['negara']}"
                    c1.markdown(teks)
                    if c2.button("→", key=f"{key}_{l.id}_{tujuan}_{r['id']}", help=f"Buka {tt.label} ini"):
                        buka_objek(tujuan, str(r["id"]))
                        st.rerun()
                if len(df) > 12:
                    st.caption(f"… {len(df) - 12} lainnya. Lihat semuanya lewat tab *Graph* atau *Ask*.")
    if dengan_aksi:
        pilihan_aksi = aksi.aksi_untuk(tipe)
        if pilihan_aksi:
            with st.expander("⚡ Aksi (Action)", expanded=False):
                a = st.selectbox("Pilih aksi", pilihan_aksi, format_func=lambda x: x.label, key=f"{key}_aksi")
                st.caption(a.deskripsi)
                nilai = {}
                for nama, label, opsi in a.parameter:
                    if opsi:
                        nilai[nama] = st.selectbox(label, opsi, key=f"{key}_{a.id}_{nama}")
                    else:
                        nilai[nama] = st.text_input(label, key=f"{key}_{a.id}_{nama}", placeholder="wajib diisi")
                if st.button(f"Jalankan: {a.label}", key=f"{key}_{a.id}_jalankan", type="primary"):
                    try:
                        aksi.jalankan(st.session_state["audit"], a.id, tipe, id_objek, judul(tipe, id_objek), nilai)
                        st.success("Aksi tercatat di jejak audit (sidebar).")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


def belajar(teks: str) -> None:
    """Expander learning mode, hanya tampil saat toggle aktif."""
    if mode_belajar:
        with st.expander("🎓 Learning mode: apa yang terjadi di sini?", expanded=True):
            st.markdown(teks)


# ----------------------------------------------------------------------------
# 6. TAB
# ----------------------------------------------------------------------------
tab_onto, tab_objek, tab_graf, tab_tanya, tab_sql, tab_data, tab_cara = st.tabs(
    ["🧭 Ontology", "🔎 Objects", "🕸️ Graph", "💬 Ask", "🧪 SQL", "📋 Data & Sources", "🛠️ How it works"])

# ---- 6.1 ONTOLOGY ------------------------------------------------------------
with tab_onto:
    st.subheader("Skema ontologi")
    st.caption("Kotak = tipe objek (object type), panah = tipe tautan (link type). Setiap tabel di SQLite diberi makna di `src/ontologi.py`.")
    kol_a, kol_b = st.columns([2.2, 1])
    with kol_a:
        st.graphviz_chart(ontologi.dot_skema(JUMLAH_OBJEK), width="stretch")
    with kol_b:
        st.markdown("**Tipe objek**")
        df_tipe = pd.DataFrame([{"Tipe": f"{t.ikon} {t.label}", "Objek": JUMLAH_OBJEK[t.id], "Properti": len(t.properti),
                                 "Tautan": len(ontologi.tautan_tipe(t.id)), "Asal data": t.asal} for t in TIPE_OBJEK.values()])
        st.dataframe(df_tipe, hide_index=True, width="stretch", height=290)
    st.markdown("**Tipe tautan**")
    df_tautan = pd.DataFrame([{"Tautan": l.label, "Dari": f"{TIPE_OBJEK[l.sumber].ikon} {TIPE_OBJEK[l.sumber].label}",
                               "Ke": f"{TIPE_OBJEK[l.tujuan].ikon} {TIPE_OBJEK[l.tujuan].label}", "Dibaca balik": l.label_balik,
                               "Kardinalitas": l.kardinalitas, "Jumlah": JUMLAH_TAUTAN[l.id],
                               "Disimpan di": f"{l.tabel}.{l.kolom_tujuan if l.kolom_sumber == 'id' else l.kolom_sumber + '/' + l.kolom_tujuan}"}
                              for l in TIPE_TAUTAN.values()])
    st.dataframe(df_tautan, hide_index=True, width="stretch", height=560)
    with st.expander("Properti tiap tipe objek"):
        pilih = st.selectbox("Tipe objek", list(TIPE_OBJEK), format_func=lambda x: f"{TIPE_OBJEK[x].ikon} {TIPE_OBJEK[x].label}")
        t = TIPE_OBJEK[pilih]
        st.caption(t.deskripsi)
        st.dataframe(pd.DataFrame([{"Properti": p.nama, "Label": p.label, "Tipe": p.tipe, "Satuan": p.satuan, "Keterangan": p.deskripsi}
                                   for p in t.properti]), hide_index=True, width="stretch")
    belajar(
        "**Ontologi** di dunia Palantir Foundry adalah lapisan semantik di atas data mentah: tabel `kapal` menjadi *object type* Kapal, "
        "kolomnya menjadi *property*, dan kolom `pemilik_id` yang menunjuk tabel `perusahaan` menjadi *link type* "
        "\"Kapal dimiliki oleh Perusahaan\". Keuntungannya: semua fitur lain (penjelajah objek, graf, mesin tanya-jawab, aksi) "
        "cukup membaca definisi ini dan tidak perlu tahu nama tabel.\n\n"
        "Di repo ini definisinya ada di `src/ontologi.py`:\n"
        "```python\n"
        "TipeTautan(\"kapal_dimiliki_oleh\", \"dimiliki oleh\", \"memiliki kapal\",\n"
        "           sumber=\"kapal\", tujuan=\"perusahaan\",\n"
        "           tabel=\"kapal\", kolom_sumber=\"id\", kolom_tujuan=\"pemilik_id\")\n"
        "```\n"
        "Tautan N:N (komoditas diproduksi di provinsi) memakai tabel penghubung `komoditas_provinsi`; polanya sama, hanya `tabel`-nya berbeda. "
        "Diagram di atas digambar langsung dari definisi itu dengan Graphviz (`ontologi.dot_skema`)."
    )

# ---- 6.2 OBJECTS -------------------------------------------------------------
with tab_objek:
    kol_kiri, kol_kanan = st.columns([1, 1.45])
    with kol_kiri:
        st.subheader("Jelajah objek")
        tipe_pilih = st.segmented_control("Tipe objek", list(TIPE_OBJEK), format_func=lambda x: f"{TIPE_OBJEK[x].ikon} {TIPE_OBJEK[x].label}",
                                          default=st.session_state["tipe_jelajah"], key="seg_tipe") or st.session_state["tipe_jelajah"]
        st.session_state["tipe_jelajah"] = tipe_pilih
        t = TIPE_OBJEK[tipe_pilih]
        cari = st.text_input("Cari nama / alias / id", key=f"cari_{tipe_pilih}", placeholder="misalnya Priok, Kaltim, nikel, KPL-057")
        filter_kat: dict[str, list[str]] = {}
        kat = t.kategori()[:3]
        if kat:
            kolom_f = st.columns(len(kat))
            for kf, p in zip(kolom_f, kat):
                opsi = [v for (v,) in kon.execute(f"SELECT DISTINCT {p.nama} FROM {tipe_pilih} WHERE {p.nama} <> '' ORDER BY 1")]
                filter_kat[p.nama] = kf.multiselect(p.label, opsi, key=f"f_{tipe_pilih}_{p.nama}")
        hasil = basis_data.cari_objek(kon, tipe_pilih, cari, filter_kat)
        st.caption(f"{angka(len(hasil))} dari {angka(JUMLAH_OBJEK[tipe_pilih])} {t.label_jamak.lower()}. Klik baris untuk membuka.")
        terpilih = tabel_objek(tipe_pilih, hasil, key=f"tabel_{tipe_pilih}", tinggi=380)
        if terpilih and st.session_state["objek"] != (tipe_pilih, terpilih):
            buka_objek(tipe_pilih, terpilih)
            st.rerun()
    with kol_kanan:
        tipe_o, id_o = st.session_state["objek"]
        if st.session_state["riwayat"]:
            jejak = " › ".join(f"{TIPE_OBJEK[tp].ikon} {judul(tp, i)}" for tp, i in st.session_state["riwayat"][-4:])
            c1, c2 = st.columns([5, 1])
            c1.caption(f"Riwayat: {jejak} › **{judul(tipe_o, id_o)}**")
            if c2.button("← Kembali", key="kembali"):
                st.session_state["objek"] = st.session_state["riwayat"].pop()
                st.rerun()
        kartu_objek(tipe_o, id_o, key="kartu_utama")
        if st.button("🕸️ Lihat di graph", key="ke_graf"):
            st.session_state["graf_akar"] = (tipe_o, id_o)
            st.toast("Akar graf diganti. Buka tab Graph.")
    belajar(
        "Ini **Object View**: satu objek, propertinya, dan semua objek lain yang terhubung, dikelompokkan per tipe tautan. "
        "Tombol → adalah **pivot**: berpindah dari objek ke tetangganya. Dari satu pelabuhan kamu bisa ke pelayaran, lalu ke kapal, "
        "lalu ke pemiliknya, lalu ke induk perusahaannya, tanpa menulis satu baris SQL.\n\n"
        "Daftar tautan dibuat generik oleh `basis_data.tetangga(kon, tipe, id)`: fungsi itu membaca semua `TipeTautan` yang menyentuh "
        "tipe objek ini dan menjalankan satu `JOIN` kecil per tautan.\n\n"
        "**Aksi (Action)** adalah cara Foundry mengubah data: bukan edit tabel langsung, tetapi operasi bernama dengan parameter yang divalidasi "
        "dan dicatat (`src/aksi.py`). Di sini jejaknya disimpan per sesi supaya basis data tetap read-only."
    )

# ---- 6.3 GRAPH ---------------------------------------------------------------
with tab_graf:
    st.subheader("Graf hubungan")
    akar = st.session_state["graf_akar"] or st.session_state["objek"]
    kol1, kol2, kol3, kol4 = st.columns([1, 1.6, 0.8, 1.6])
    tipe_akar = kol1.selectbox("Tipe akar", list(TIPE_OBJEK), index=list(TIPE_OBJEK).index(akar[0]),
                               format_func=lambda x: f"{TIPE_OBJEK[x].ikon} {TIPE_OBJEK[x].label}", key="graf_tipe")
    daftar_akar = basis_data.semua_objek(kon, tipe_akar)
    opsi_akar = daftar_akar["id"].tolist()
    nama_akar = dict(zip(daftar_akar["id"], daftar_akar[TIPE_OBJEK[tipe_akar].kolom_judul]))
    idx = opsi_akar.index(akar[1]) if (akar[0] == tipe_akar and akar[1] in opsi_akar) else 0
    id_akar = kol2.selectbox("Objek akar", opsi_akar, index=idx, format_func=lambda x: f"{nama_akar[x]} ({x})", key="graf_id")
    kedalaman = kol3.slider("Kedalaman", 1, 3, 2, key="graf_dalam", help="Berapa lompatan tautan dari akar")
    tautan_aktif = kol4.multiselect("Tipe tautan yang diikuti", list(TIPE_TAUTAN), default=list(TIPE_TAUTAN),
                                    format_func=lambda x: TIPE_TAUTAN[x].label, key="graf_tautan")
    lewati_pelayaran = st.toggle("Jangan ekspansi lewat pelayaran dan insiden (ringkas)", value=True,
                                 help="Pelayaran dan insiden tetap digambar, tetapi tidak diteruskan ke tetangganya supaya graf tidak meledak.")
    g = graf.subgraf(kon, tipe_akar, id_akar, kedalaman, set(tautan_aktif), batas=graf.BATAS_SIMPUL,
                     tipe_dilewati={"pelayaran", "insiden"} if lewati_pelayaran else set())
    kg1, kg2 = st.columns([3.2, 1])
    with kg1:
        fig = graf.gambar_graf(g, graf.kunci(tipe_akar, id_akar))
        ev = st.plotly_chart(fig, width="stretch", key="graf_plot", on_select="rerun", selection_mode="points")
        titik = ev.selection.points if ev and ev.selection else []
        if g.number_of_nodes() >= graf.BATAS_SIMPUL:
            st.caption(f"Graf dipotong pada {graf.BATAS_SIMPUL} simpul supaya tetap terbaca. Kurangi kedalaman atau matikan beberapa tautan.")
    with kg2:
        st.markdown(f"**{g.number_of_nodes()} simpul · {g.number_of_edges()} sisi**")
        st.dataframe(graf.ringkasan_graf(g), hide_index=True, width="stretch")
        if titik and titik[0].get("customdata"):
            tp, idp = graf.pisah(str(titik[0]["customdata"]))
            st.markdown(f"Dipilih: {TIPE_OBJEK[tp].ikon} **{judul(tp, idp)}**")
            if st.button("Buka objek ini", key="graf_buka"):
                buka_objek(tp, idp)
                st.session_state["graf_akar"] = (tp, idp)
                st.rerun()
            if st.button("Jadikan akar graf", key="graf_akar_btn"):
                st.session_state["graf_akar"] = (tp, idp)
                st.rerun()
        else:
            st.caption("Klik satu simpul untuk membukanya atau menjadikannya akar baru. Hover untuk melihat properti.")
    belajar(
        "Graf ini dibangun dengan **BFS** (breadth-first search) dari objek akar: ambil semua tetangga lewat tautan yang diizinkan, "
        "lalu tetangga dari tetangga, sampai kedalaman yang diminta atau batas simpul tercapai (`graf.subgraf`). Tata letaknya "
        "`networkx.spring_layout`: simpul yang terhubung saling tarik, yang tidak saling tolak.\n\n"
        "Inilah inti analisis graf ala Gotham: dari satu kapal yang kena insiden, dua lompatan sudah menunjukkan pemiliknya, "
        "induk perusahaannya, kapal saudaranya, dan pelabuhan yang sama-sama mereka singgahi. Pelayaran dan insiden adalah "
        "*event object*, jumlahnya ratusan, sehingga secara bawaan tidak diekspansi lebih lanjut."
    )

# ---- 6.4 ASK -----------------------------------------------------------------
with tab_tanya:
    st.subheader("Tanya ontologi")
    st.caption("Tanpa model bahasa: pertanyaan dipecah menjadi tipe objek target, objek yang disebut, lalu jalur tautan di skema, "
               "dan disusun menjadi SQL yang bisa kamu baca. Coba contoh di bawah atau ketik sendiri.")
    kolom_contoh = st.columns(3)
    for i, contoh in enumerate(kueri.CONTOH_PERTANYAAN[:9]):
        if kolom_contoh[i % 3].button(contoh, key=f"contoh_{i}", width="stretch"):
            st.session_state["pertanyaan_tertunda"] = contoh
    with st.expander("Contoh lain"):
        for contoh in kueri.CONTOH_PERTANYAAN[9:] + ["Kapal yang pernah mengalami insiden", "Komoditas yang diangkut kapal asing",
                                                      "Kapal mana yang paling sering kena insiden", "Induk dari Nusantara Bulk Carriers"]:
            st.markdown(f"- {contoh}")

    def jawab(pertanyaan: str) -> dict:
        r = kueri.rencanakan(kon, pertanyaan, st.session_state["konteks_chat"])
        df, kalimat = kueri.jalankan(kon, r)
        if r.jangkar and any(e.id for e in r.jangkar):
            st.session_state["konteks_chat"] = [e for e in r.jangkar if e.id]
        return {"rencana": r, "df": df, "kalimat": kalimat}

    def tampilkan_jawaban(j: dict, key: str) -> None:
        r: kueri.Rencana = j["rencana"]
        if r.maksud == "bantuan":
            st.markdown("Pertanyaan belum dikenali. Sebutkan **tipe objek** yang kamu cari (kapal, pelabuhan, komoditas, perusahaan, provinsi, "
                        "pelayaran, insiden) dan/atau **nama objek** (Balikpapan, batu bara, Nusantara Bulk, Kaltim). Contoh: "
                        "*kapal apa saja yang dimiliki Meridian*, *berapa pelayaran ke Shanghai tahun 2025*, *pelabuhan tersibuk*.")
            return
        if r.maksud == "detail":
            e = r.jangkar[0]
            kartu_objek(e.tipe, e.id, key=key, dengan_aksi=False, ringkas=True)
            if st.button("Buka di tab Objects", key=f"{key}_buka"):
                buka_objek(e.tipe, e.id)
                st.toast("Objek dibuka di tab Objects.")
            return
        st.markdown(j["kalimat"])
        df: pd.DataFrame = j["df"]
        with st.expander("Bagaimana jawaban ini dihitung", expanded=mode_belajar):
            for baris in r.penjelasan:
                st.markdown(baris)
            st.code(r.sql + ("\n-- parameter: " + ", ".join(repr(p) for p in r.params) if r.params else ""), language="sql")
        if r.maksud == "hitung" or df.empty:
            return
        t = TIPE_OBJEK[r.tipe_target]
        if r.maksud == "peringkat":
            fig = px.bar(df.head(10), x="jumlah", y=t.kolom_judul, orientation="h", color_discrete_sequence=[t.warna],
                         labels={"jumlah": f"jumlah {TIPE_OBJEK[r.tipe_ukur].label_jamak.lower()}", t.kolom_judul: ""})
            fig.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(rapikan(fig, 320), width="stretch", key=f"{key}_bar")
        tampil = kolom_tampil(r.tipe_target, df)
        if "jumlah" in df.columns:
            tampil.insert(1, "Jumlah", df["jumlah"].values)
        st.dataframe(tampil, hide_index=True, width="stretch", height=min(400, 38 + 35 * len(tampil)))
        if r.jangkar and r.jangkar[0].id:
            e = r.jangkar[0]
            if st.button(f"🕸️ Lihat {TIPE_OBJEK[e.tipe].label.lower()} «{e.nama}» di graph", key=f"{key}_graf"):
                st.session_state["graf_akar"] = (e.tipe, e.id)
                st.toast("Akar graf diganti. Buka tab Graph.")

    for i, (peran, isi) in enumerate(st.session_state["chat"]):
        with st.chat_message(peran):
            if peran == "user":
                st.markdown(isi)
            else:
                tampilkan_jawaban(isi, key=f"jawab_{i}")
    pertanyaan = st.chat_input("Tanya apa saja tentang kapal, pelabuhan, komoditas, perusahaan…", key="chat_input")
    if st.session_state["pertanyaan_tertunda"]:
        pertanyaan = st.session_state["pertanyaan_tertunda"]
        st.session_state["pertanyaan_tertunda"] = None
    if pertanyaan:
        st.session_state["chat"].append(("user", pertanyaan))
        st.session_state["chat"].append(("assistant", jawab(pertanyaan)))
        st.rerun()
    if st.session_state["chat"] and st.button("Bersihkan percakapan", key="bersih_chat"):
        st.session_state["chat"], st.session_state["konteks_chat"] = [], []
        st.rerun()
    belajar(
        "Mesin tanya-jawab ini (`src/kueri.py`) bekerja dalam lima langkah yang semuanya deterministik:\n\n"
        "1. **Entitas**: cocokkan nama/alias objek dari basis data (\"Balikpapan\", \"Kaltim\", \"batu bara\", \"KPL-057\").\n"
        "2. **Tipe target**: kata benda tipe objek yang ditanyakan (\"kapal apa\", \"berapa pelayaran\").\n"
        "3. **Maksud**: daftar, hitung (*berapa*), peringkat (*terbanyak*), urut properti (*terbesar*, *tertua*), atau detail.\n"
        "4. **Jalur**: BFS di graf *skema* dari tipe target ke tipe entitas; kata petunjuk (\"dari\", \"ke\", \"dimiliki\") memilih tautan "
        "kalau ada lebih dari satu (pelayaran berangkat dari / tiba di pelabuhan).\n"
        "5. **SQL**: `SELECT DISTINCT target JOIN ... JOIN ... WHERE entitas.id = ?` plus filter tahun/kategori.\n\n"
        "Konsep ini sama dengan **object set + search around** di Foundry: pertanyaan = himpunan objek yang didapat dengan melompat "
        "lewat tautan dari objek yang disebut. Pengembangan wajar berikutnya adalah menambahkan model bahasa untuk menerjemahkan "
        "pertanyaan bebas menjadi rencana terstruktur yang sama, seperti di proyek talk-to-the-data."
    )

# ---- 6.5 SQL -----------------------------------------------------------------
with tab_sql:
    st.subheader("Konsol SQL (read-only)")
    ks1, ks2 = st.columns([1.6, 1])
    with ks1:
        contoh_sql = (
            "-- Komoditas apa yang paling banyak diangkut, dan berapa total muatannya?\n"
            "SELECT k.nama AS komoditas, COUNT(*) AS pelayaran, SUM(v.muatan) AS total_muatan\n"
            "FROM pelayaran v\n"
            "JOIN komoditas k ON k.id = v.komoditas_id\n"
            "GROUP BY k.nama\n"
            "ORDER BY total_muatan DESC"
        )
        sql = st.text_area("SQL", value=contoh_sql, height=200, key="sql_teks")
        if st.button("Jalankan", type="primary", key="sql_jalankan"):
            try:
                hasil_sql = basis_data.jalankan_sql_aman(kon, sql)
                st.session_state["sql_hasil"] = hasil_sql
            except basis_data.KesalahanSQL as e:
                st.error(f"Kueri ditolak: {e}")
        if "sql_hasil" in st.session_state:
            hs = st.session_state["sql_hasil"]
            st.caption(f"{angka(len(hs))} baris (maksimal 500).")
            st.dataframe(hs, hide_index=True, width="stretch", height=min(420, 38 + 35 * len(hs)))
            st.download_button("Unduh CSV", hs.to_csv(index=False).encode(), "hasil_sql.csv", "text/csv", key="sql_unduh")
    with ks2:
        st.markdown("**Skema**")
        for t in TIPE_OBJEK.values():
            with st.expander(f"{t.ikon} {t.id}  ({JUMLAH_OBJEK[t.id]} baris)"):
                kolom_fk = [l.kolom_tujuan for l in TIPE_TAUTAN.values() if l.tabel == t.id and l.kolom_sumber == "id"]
                st.markdown("\n".join(f"- `{p.nama}` {p.tipe}" + (f" · {p.deskripsi}" if p.deskripsi else "") for p in t.properti)
                            + "".join(f"\n- `{k}` → {TIPE_OBJEK[[l.tujuan for l in TIPE_TAUTAN.values() if l.tabel == t.id and l.kolom_tujuan == k][0]].id}.id"
                                      for k in kolom_fk))
        for nama in basis_data.TABEL_PENGHUBUNG:
            with st.expander(f"🔗 {nama} (tabel penghubung)"):
                kolom = [c[1] for c in kon.execute(f"PRAGMA table_info({nama})")]
                st.markdown("\n".join(f"- `{k}`" for k in kolom))
        st.markdown("**Contoh lain**")
        st.code("SELECT p.nama, COUNT(*) AS n\nFROM insiden i JOIN pelabuhan p ON p.id = i.pelabuhan_id\n"
                "GROUP BY p.nama ORDER BY n DESC LIMIT 5", language="sql")
        st.code("SELECT k.nama, k.bendera, COUNT(i.id) AS insiden\nFROM kapal k LEFT JOIN insiden i ON i.kapal_id = k.id\n"
                "WHERE k.bendera <> 'Indonesia'\nGROUP BY k.id ORDER BY insiden DESC", language="sql")
    belajar(
        "Ontologi tidak menggantikan SQL; ia duduk di atasnya. Konsol ini membuka SQLite yang sama yang dipakai semua tab lain, dalam "
        "mode `PRAGMA query_only` dan dengan pemeriksaan tambahan (`basis_data.jalankan_sql_aman`): hanya satu pernyataan `SELECT`, "
        "kata kunci penulisan ditolak, hasil dibatasi 500 baris. Bandingkan SQL yang kamu tulis sendiri dengan SQL yang dihasilkan "
        "tab *Ask* untuk pertanyaan yang sama."
    )

# ---- 6.6 DATA & SOURCES ------------------------------------------------------
with tab_data:
    st.subheader("Data & sumber")
    st.markdown(
        "| Data | Asal | Keterangan |\n|---|---|---|\n"
        "| `provinsi.csv` | Nyata | 38 provinsi, kode ISO 3166-2, pulau, ibu kota, penduduk pertengahan 2023 (BPS, dibulatkan 0,1 juta), koordinat ibu kota |\n"
        "| `pelabuhan.csv` | Nyata | 30 pelabuhan Indonesia (kode UN/LOCODE, operator, kelas, koordinat perkiraan) dan 12 hub luar negeri |\n"
        "| `komoditas.csv`, `komoditas_provinsi.csv` | Nyata | 21 komoditas utama perdagangan laut, bab HS, moda angkut, arah perdagangan; provinsi penghasil utama dari statistik produksi BPS dan kementerian |\n"
        "| `perusahaan.csv` (operator pelabuhan) | Nyata | Pelindo dan empat regionalnya, Pelabuhan Patimban Internasional, BP Batam, Krakatau Bandar Samudera, dari informasi publik |\n"
        "| `perusahaan.csv` (lainnya), `perusahaan_komoditas.csv` | Sintetis | 29 perusahaan fiktif dengan struktur grup, kantor pusat, dan komoditas yang ditangani |\n"
        "| `kapal.csv` | Sintetis | 63 kapal: jenis mengikuti moda komoditas pemiliknya, DWT dalam rentang wajar per jenis, bendera asing untuk pemilik asing |\n"
        "| `pelayaran.csv` | Sintetis | 520 pelayaran 2024-2026: asal dari provinsi penghasil, tujuan pasar ekspor yang lazim atau hub domestik, durasi dari jarak haversine, aturan cabotage (rute domestik hanya kapal berbendera Indonesia) |\n"
        "| `insiden.csv` | Sintetis | 90 insiden: kapal tua dan berbendera asing lebih sering terkena, lokasi dan tanggal diambil dari pelayarannya |\n"
    )
    st.caption("Rincian, alasan pemilihan, dan keterbatasan ada di `data/SUMBER_DATA.md`. Bangun ulang dengan `python scripts/bangun_data.py`.")
    masalah = basis_data.cek_integritas(kon)
    if masalah:
        st.error("Integritas referensi: " + "; ".join(masalah))
    else:
        st.success(f"Integritas referensi OK: semua {angka(TOTAL_TAUTAN)} tautan menunjuk objek yang ada.")
    st.markdown("**Unduh**")
    kol_unduh = st.columns(4)
    for i, nama in enumerate(list(TIPE_OBJEK) + basis_data.TABEL_PENGHUBUNG):
        df = basis_data.sql_df(kon, f"SELECT * FROM {nama}")
        kol_unduh[i % 4].download_button(f"{nama}.csv ({len(df)})", df.to_csv(index=False).encode(), f"{nama}.csv", "text/csv",
                                         key=f"unduh_{nama}", width="stretch")
    st.markdown("**Mengapa sebagian data disintesis?** Data AIS pelayaran per kapal, manifes muatan, dan daftar pemilik kapal yang lengkap tidak "
                "tersedia sebagai data terbuka. Daripada menebak-nebak perusahaan nyata, generator membuat dunia kecil yang konsisten: "
                "setiap pelayaran punya kapal yang jenisnya cocok dengan komoditas, berangkat dari provinsi yang memang menghasilkan komoditas itu, "
                "dan menuju pasar yang memang membelinya. Fokus proyek ini adalah **cara ontologi menghubungkan data**, bukan angkanya.")

# ---- 6.7 HOW IT WORKS --------------------------------------------------------
with tab_cara:
    st.subheader("Cara kerja")
    st.graphviz_chart(
        'digraph alur { rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="#141b2d" fontcolor="#e6edf3" '
        'color="#3b4863" fontname="Helvetica" fontsize=11]; edge [color="#7d8aa0"];\n'
        'gen [label="scripts/bangun_data.py\\nreferensi nyata + generator sintetis"];\n'
        'csv [label="data/*.csv\\n7 tabel objek + 2 tabel penghubung" shape=cylinder];\n'
        'onto [label="src/ontologi.py\\ntipe objek · properti · tipe tautan" fillcolor="#3a2f0b" color="#fbbf24"];\n'
        'db [label="src/basis_data.py\\nSQLite in-memory, akses generik"];\n'
        'q [label="src/kueri.py\\npertanyaan → himpunan objek → SQL"];\n'
        'g [label="src/graf.py\\nBFS + networkx + Plotly"];\n'
        'a [label="src/aksi.py\\naksi + jejak audit"];\n'
        'ui [label="app.py\\nObjects · Graph · Ask · SQL" fillcolor="#0f2a3a" color="#22d3ee"];\n'
        'gen -> csv -> db; onto -> db; onto -> q; onto -> g; db -> q; db -> g; q -> ui; g -> ui; a -> ui; db -> ui; }',
        width="stretch")
    st.markdown(
        "| Istilah Foundry | Di proyek ini | File |\n|---|---|---|\n"
        "| Object type | `TipeObjek` (Provinsi, Pelabuhan, Kapal, …) | `src/ontologi.py` |\n"
        "| Property | `Properti` dengan tipe teks/angka/tanggal/kategori | `src/ontologi.py` |\n"
        "| Link type | `TipeTautan` dengan label dua arah dan kolom penyimpan | `src/ontologi.py` |\n"
        "| Backing dataset | tabel SQLite yang dimuat dari CSV | `src/basis_data.py` |\n"
        "| Object view | kartu objek + tautan per tipe + tombol pivot | `app.py` (tab Objects) |\n"
        "| Object set / search around | `Rencana` dari pertanyaan: target, pivot, filter | `src/kueri.py` |\n"
        "| Graph explorer | BFS dari akar, gambar Plotly | `src/graf.py` |\n"
        "| Action + audit | `DefinisiAksi`, `CatatanAudit` | `src/aksi.py` |\n"
    )
    st.markdown("**Modul**")
    st.markdown(
        "| Modul | Yang dilakukan |\n|---|---|\n"
        "| `scripts/bangun_data.py` | Menulis data referensi nyata dan membangkitkan data operasional sintetis dengan seed tetap |\n"
        "| `src/ontologi.py` | Mendefinisikan skema; BFS jalur antar tipe; diagram DOT |\n"
        "| `src/basis_data.py` | Memuat CSV ke SQLite; pencarian, tetangga, konsol SQL aman, cek integritas |\n"
        "| `src/kueri.py` | Perencana pertanyaan: entitas, tipe target, maksud, jalur, SQL, kalimat jawaban |\n"
        "| `src/graf.py` | Subgraf BFS, tata letak, gambar Plotly, ringkasan |\n"
        "| `src/aksi.py` | Definisi aksi, validasi parameter, jejak audit |\n"
        "| `app.py` | UI Streamlit: sidebar, tujuh tab, learning mode |\n"
    )
    belajar(
        "Kalau kamu ingin **menambah tipe objek baru** (misalnya *Smelter*): (1) tambahkan daftar referensinya di `scripts/bangun_data.py` dan "
        "jalankan ulang, (2) daftarkan `TipeObjek(\"smelter\", ...)` plus `TipeTautan` yang menghubungkannya (misalnya Smelter —memproses→ Komoditas, "
        "Smelter —terletak di→ Provinsi) di `src/ontologi.py`, (3) jalankan `pytest`. Tab Objects, Graph, Ask, dan SQL otomatis mengenalnya, "
        "termasuk pertanyaan seperti *smelter di Sulawesi Tengah*."
    )
