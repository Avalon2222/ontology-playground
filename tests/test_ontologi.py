"""Skema ontologi harus konsisten dengan basis data dan bisa dinavigasi."""

import pytest

from src import basis_data, ontologi
from src.ontologi import TIPE_OBJEK, TIPE_TAUTAN


@pytest.fixture(scope="module")
def kon():
    return basis_data.buat_koneksi()


def kolom_tabel(kon, tabel):
    return {baris[1] for baris in kon.execute(f"PRAGMA table_info({tabel})")}


def test_tautan_menunjuk_tipe_yang_ada():
    for l in TIPE_TAUTAN.values():
        assert l.sumber in TIPE_OBJEK and l.tujuan in TIPE_OBJEK, l.id
        assert l.label and l.label_balik and l.kardinalitas in ("1:N", "N:1", "N:N")


def test_tabel_dan_kolom_tautan_ada_di_basis_data(kon):
    for l in TIPE_TAUTAN.values():
        kolom = kolom_tabel(kon, l.tabel)
        assert l.kolom_sumber in kolom and l.kolom_tujuan in kolom, l.id


def test_properti_ada_di_tabel(kon):
    for t in TIPE_OBJEK.values():
        kolom = kolom_tabel(kon, t.tabel)
        for p in t.properti:
            assert p.nama in kolom, f"{t.id}.{p.nama}"
        assert t.kolom_judul in kolom
        if t.kolom_alias:
            assert t.kolom_alias in kolom
        assert any(p.tipe == "id" for p in t.properti)


def test_sinonim_tidak_tumpang_tindih_antar_tipe():
    terlihat = {}
    for t in TIPE_OBJEK.values():
        for s in t.sinonim:
            assert s not in terlihat, f"'{s}' dipakai {terlihat.get(s)} dan {t.id}"
            terlihat[s] = t.id


def test_tetangga_tipe_simetris():
    for a in TIPE_OBJEK:
        for b in ontologi.tetangga_tipe(a):
            assert a in ontologi.tetangga_tipe(b)


@pytest.mark.parametrize("dari,ke,panjang", [
    ("kapal", "perusahaan", 2), ("kapal", "pelabuhan", 3), ("komoditas", "provinsi", 2), ("insiden", "komoditas", 3),
    ("provinsi", "provinsi", 1), ("kapal", "kapal", 1),
])
def test_jalur_terpendek(dari, ke, panjang):
    jalur = ontologi.jalur_terpendek(dari, ke)
    assert jalur is not None and len(jalur) == panjang
    assert jalur[0] == dari and jalur[-1] == ke


def test_semua_tipe_saling_terhubung():
    for a in TIPE_OBJEK:
        for b in TIPE_OBJEK:
            assert ontologi.jalur_terpendek(a, b) is not None


def test_tautan_antara_pelayaran_pelabuhan_ada_dua():
    ids = {l.id for l in ontologi.tautan_antara("pelayaran", "pelabuhan")}
    assert ids == {"pelayaran_berangkat_dari", "pelayaran_tiba_di"}
    assert [l.id for l in ontologi.tautan_antara("perusahaan", "perusahaan")] == ["perusahaan_anak_dari"]


def test_dot_skema_memuat_semua_tipe_dan_tautan():
    dot = ontologi.dot_skema({"kapal": 63}, sorot="kapal")
    for t in TIPE_OBJEK.values():
        assert f"{t.id} [" in dot
    for l in TIPE_TAUTAN.values():
        assert f"{l.sumber} -> {l.tujuan}" in dot
    assert "63 objek" in dot and "penwidth=3" in dot


def test_label_dari_mengikuti_arah():
    l = TIPE_TAUTAN["kapal_dimiliki_oleh"]
    assert l.label_dari("kapal") == "dimiliki oleh"
    assert l.label_dari("perusahaan") == "memiliki kapal"
    assert l.ujung_lain("kapal") == "perusahaan"


def test_ringkasan_skema():
    teks = ontologi.ringkasan_skema()
    assert "Kapal --dimiliki oleh--> Perusahaan" in teks and "dwt (angka)" in teks
