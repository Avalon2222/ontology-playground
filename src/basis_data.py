"""
basis_data.py - Memuat CSV di data/ ke SQLite (in-memory) dan menyediakan fungsi akses yang sadar ontologi.

Mengapa SQLite? Bawaan Python (tanpa dependensi), cukup cepat untuk ribuan baris, dan SQL-nya bisa
ditampilkan apa adanya kepada pengguna sebagai bahan belajar. Seluruh nama tabel/kolom diambil dari
src/ontologi.py, sehingga fungsi di sini bersifat generik: `tetangga()` bekerja untuk tipe objek apa pun.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src import ontologi
from src.ontologi import TIPE_OBJEK, TIPE_TAUTAN, TipeTautan

DIR_DATA = Path(__file__).resolve().parent.parent / "data"

# tabel penghubung (N:N) yang tidak menjadi tipe objek
TABEL_PENGHUBUNG = sorted({t.tabel for t in TIPE_TAUTAN.values()} - set(TIPE_OBJEK))

_KATA_TERLARANG = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b", re.IGNORECASE)


class KesalahanSQL(ValueError):
    """SQL ditolak sebelum dijalankan (bukan SELECT, atau mengandung perintah tulis)."""


def muat_tabel(nama: str, dir_data: Path = DIR_DATA) -> pd.DataFrame:
    df = pd.read_csv(dir_data / f"{nama}.csv", dtype=str, keep_default_na=False)
    # kolom angka dikembalikan ke numerik; kolom lain tetap teks (id dan kode seperti '09' tidak boleh berubah)
    for kolom in df.columns:
        if kolom in {"lat", "lon", "penduduk_juta", "dwt", "panjang_m", "tahun_dibangun", "tahun_berdiri", "muatan",
                     "jarak_km", "hari_tertahan", "peringkat"}:
            df[kolom] = pd.to_numeric(df[kolom], errors="coerce")
    return df


def buat_koneksi(dir_data: Path = DIR_DATA) -> sqlite3.Connection:
    """Bangun basis data in-memory dari semua CSV. Dipanggil sekali per proses (di app lewat st.cache_resource)."""
    kon = sqlite3.connect(":memory:", check_same_thread=False)
    for nama in list(TIPE_OBJEK) + TABEL_PENGHUBUNG:
        muat_tabel(nama, dir_data).to_sql(nama, kon, index=False)
    kursor = kon.cursor()
    for t in TIPE_OBJEK.values():
        kursor.execute(f"CREATE UNIQUE INDEX idx_{t.id}_id ON {t.id}(id)")
    for l in TIPE_TAUTAN.values():
        kursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{l.tabel}_{l.kolom_tujuan} ON {l.tabel}({l.kolom_tujuan})")
        kursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{l.tabel}_{l.kolom_sumber} ON {l.tabel}({l.kolom_sumber})")
    kon.commit()
    kon.execute("PRAGMA query_only = 1")   # setelah dimuat, koneksi hanya boleh membaca
    return kon


def sql_df(kon: sqlite3.Connection, sql: str, params: tuple | list = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, kon, params=params)


def jalankan_sql_aman(kon: sqlite3.Connection, sql: str, batas: int = 500) -> pd.DataFrame:
    """Konsol SQL untuk pengguna: hanya SELECT/WITH tunggal, tanpa perintah tulis, hasil dibatasi."""
    bersih = sql.strip().rstrip(";").strip()
    if not bersih:
        raise KesalahanSQL("Kueri kosong.")
    if ";" in bersih:
        raise KesalahanSQL("Hanya satu pernyataan per kueri.")
    if not re.match(r"^(select|with)\b", bersih, re.IGNORECASE):
        raise KesalahanSQL("Hanya SELECT (atau WITH ... SELECT) yang diizinkan.")
    if _KATA_TERLARANG.search(bersih):
        raise KesalahanSQL("Kueri mengandung perintah yang tidak diizinkan.")
    try:
        return sql_df(kon, f"SELECT * FROM ({bersih}) LIMIT {int(batas)}")
    except Exception as e:   # noqa: BLE001 - pesan SQLite diteruskan apa adanya ke pengguna
        raise KesalahanSQL(str(e)) from e


# ---------------------------------------------------------------------------
# AKSES OBJEK
# ---------------------------------------------------------------------------
def hitung_objek(kon: sqlite3.Connection) -> dict[str, int]:
    return {t.id: kon.execute(f"SELECT COUNT(*) FROM {t.id}").fetchone()[0] for t in TIPE_OBJEK.values()}


def hitung_tautan(kon: sqlite3.Connection) -> dict[str, int]:
    hasil = {}
    for l in TIPE_TAUTAN.values():
        hasil[l.id] = kon.execute(
            f"SELECT COUNT(*) FROM {l.tabel} WHERE {l.kolom_tujuan} <> '' AND {l.kolom_sumber} <> ''").fetchone()[0]
    return hasil


def semua_objek(kon: sqlite3.Connection, tipe: str) -> pd.DataFrame:
    return sql_df(kon, f"SELECT * FROM {tipe} ORDER BY {TIPE_OBJEK[tipe].kolom_judul}")


def ambil_objek(kon: sqlite3.Connection, tipe: str, id_objek: str) -> dict | None:
    baris = sql_df(kon, f"SELECT * FROM {tipe} WHERE id = ?", (id_objek,))
    return None if baris.empty else baris.iloc[0].to_dict()


def judul_objek(kon: sqlite3.Connection, tipe: str, id_objek: str) -> str:
    o = ambil_objek(kon, tipe, id_objek)
    if o is None:
        return id_objek
    judul = str(o[TIPE_OBJEK[tipe].kolom_judul])
    if tipe == "pelayaran":
        judul = f"{o['id']} · {o['berangkat']}"
    if tipe == "insiden":
        judul = f"{o['id']} · {o['jenis']}"
    return judul


def cari_objek(kon: sqlite3.Connection, tipe: str, teks: str = "", filter_kategori: dict[str, list[str]] | None = None,
               batas: int = 500) -> pd.DataFrame:
    """Pencarian teks pada nama/alias/id + filter kategori (nilai dalam daftar)."""
    t = TIPE_OBJEK[tipe]
    syarat, params = [], []
    if teks:
        kolom_cari = [t.kolom_judul, "id"] + ([t.kolom_alias] if t.kolom_alias else [])
        syarat.append("(" + " OR ".join(f"LOWER({k}) LIKE ?" for k in kolom_cari) + ")")
        params += [f"%{teks.lower()}%"] * len(kolom_cari)
    for kolom, nilai in (filter_kategori or {}).items():
        if nilai:
            syarat.append(f"{kolom} IN ({','.join('?' * len(nilai))})")
            params += list(nilai)
    where = ("WHERE " + " AND ".join(syarat)) if syarat else ""
    return sql_df(kon, f"SELECT * FROM {tipe} {where} ORDER BY {t.kolom_judul} LIMIT {int(batas)}", params)


def sql_tetangga(l: TipeTautan, dari_tipe: str) -> str:
    """SQL untuk melompat satu tautan dari objek bertipe `dari_tipe` ke ujung lain tautan `l`."""
    tujuan = l.ujung_lain(dari_tipe)
    if dari_tipe == l.sumber:
        kolom_sini, kolom_sana = l.kolom_sumber, l.kolom_tujuan
    else:
        kolom_sini, kolom_sana = l.kolom_tujuan, l.kolom_sumber
    return (f"SELECT t.* FROM {tujuan} t JOIN {l.tabel} r ON r.{kolom_sana} = t.id "
            f"WHERE r.{kolom_sini} = ? ORDER BY t.{TIPE_OBJEK[tujuan].kolom_judul}")


def tetangga(kon: sqlite3.Connection, tipe: str, id_objek: str) -> list[tuple[TipeTautan, str, pd.DataFrame]]:
    """Semua objek yang terhubung langsung, per tipe tautan: [(tautan, tipe_tujuan, DataFrame), ...]."""
    hasil = []
    for l in ontologi.tautan_tipe(tipe):
        arah = [l.sumber == tipe, l.tujuan == tipe]
        # tautan ke tipe sendiri (perusahaan -> perusahaan) dibaca dua arah
        for sebagai_sumber, aktif in zip((True, False), arah):
            if not aktif:
                continue
            tujuan = l.tujuan if sebagai_sumber else l.sumber
            kolom_sini = l.kolom_sumber if sebagai_sumber else l.kolom_tujuan
            kolom_sana = l.kolom_tujuan if sebagai_sumber else l.kolom_sumber
            df = sql_df(kon, f"SELECT t.* FROM {tujuan} t JOIN {l.tabel} r ON r.{kolom_sana} = t.id "
                             f"WHERE r.{kolom_sini} = ? ORDER BY t.{TIPE_OBJEK[tujuan].kolom_judul}", (id_objek,))
            label = l.label if sebagai_sumber else l.label_balik
            hasil.append((TipeTautan(l.id, label, label, tipe, tujuan, l.tabel, kolom_sini, kolom_sana, l.kardinalitas,
                                     l.deskripsi, l.kata_kunci), tujuan, df))
    return hasil


def semua_sisi(kon: sqlite3.Connection) -> pd.DataFrame:
    """Seluruh tautan sebagai tabel sisi graf: tipe_tautan, sumber, tujuan (id dengan awalan tipe)."""
    bagian = []
    for l in TIPE_TAUTAN.values():
        df = sql_df(kon, f"SELECT {l.kolom_sumber} AS s, {l.kolom_tujuan} AS t FROM {l.tabel} "
                         f"WHERE {l.kolom_sumber} <> '' AND {l.kolom_tujuan} <> ''")
        df["tautan"] = l.id
        df["sumber"] = l.sumber + ":" + df["s"]
        df["tujuan"] = l.tujuan + ":" + df["t"]
        bagian.append(df[["tautan", "sumber", "tujuan"]])
    return pd.concat(bagian, ignore_index=True)


def cek_integritas(kon: sqlite3.Connection) -> list[str]:
    """Setiap kolom penunjuk (foreign key) harus menunjuk id yang ada. Mengembalikan daftar masalah (kosong = sehat)."""
    masalah = []
    for l in TIPE_TAUTAN.values():
        for kolom, tipe in ((l.kolom_sumber, l.sumber), (l.kolom_tujuan, l.tujuan)):
            if kolom == "id" and l.tabel == tipe:
                continue
            n = kon.execute(f"SELECT COUNT(*) FROM {l.tabel} r LEFT JOIN {tipe} o ON o.id = r.{kolom} "
                            f"WHERE r.{kolom} <> '' AND o.id IS NULL").fetchone()[0]
            if n:
                masalah.append(f"{l.tabel}.{kolom}: {n} baris menunjuk {tipe} yang tidak ada")
    return masalah
